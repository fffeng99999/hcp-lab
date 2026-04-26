package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"hcp-lab-server/internal/ai"
	"hcp-lab-server/internal/experiments"
	"hcp-lab-server/internal/runner"
	"hcp-lab-server/internal/store"
	"hcp-lab-server/internal/ws"
)

type apiResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Data    any    `json:"data,omitempty"`
}

func respJSON(w http.ResponseWriter, code int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(apiResponse{Code: 0, Message: "ok", Data: data})
}

func respError(w http.ResponseWriter, code int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(apiResponse{Code: code, Message: msg})
}

func enableCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func main() {
	var (
		port        = flag.String("port", "9090", "server port")
		projectRoot = flag.String("root", ".", "project root directory (parent of hcp-lab)")
		aiAPIURL    = flag.String("ai-url", "https://api.openai.com/v1/chat/completions", "AI API URL")
		aiAPIKey    = flag.String("ai-key", "", "AI API key")
		aiModel     = flag.String("ai-model", "gpt-4", "AI model name")
		aiTimeout   = flag.Int("ai-timeout", 120, "AI API timeout (seconds)")
	)
	flag.Parse()

	absRoot, err := filepath.Abs(*projectRoot)
	if err != nil {
		log.Fatal(err)
	}

	dataDir := filepath.Join(absRoot, "hcp-lab", "hcp-lab-server", "data")
	st, err := store.New(dataDir)
	if err != nil {
		log.Fatal("store init:", err)
	}

	hub := ws.NewHub()
	go hub.Run()

	rnr := runner.New(absRoot, st, hub)

	aiConfig := ai.AIConfig{
		APIURL:  *aiAPIURL,
		APIKey:  *aiAPIKey,
		Model:   *aiModel,
		Timeout: *aiTimeout,
	}
	aiSvc, err := ai.NewService(aiConfig)
	if err != nil {
		log.Fatal("ai service init:", err)
	}

	mux := http.NewServeMux()

	// Health check
	mux.HandleFunc("/api/health", func(w http.ResponseWriter, r *http.Request) {
		respJSON(w, 200, map[string]string{"status": "ok"})
	})

	// List experiments
	mux.HandleFunc("/api/experiments", func(w http.ResponseWriter, r *http.Request) {
		respJSON(w, 200, experiments.Registry)
	})

	// Get single experiment
	mux.HandleFunc("/api/experiments/", func(w http.ResponseWriter, r *http.Request) {
		path := strings.TrimPrefix(r.URL.Path, "/api/experiments/")
		parts := strings.Split(path, "/")
		if len(parts) == 0 || parts[0] == "" {
			respError(w, 400, "missing experiment id")
			return
		}
		id := parts[0]
		exp, ok := experiments.FindByID(id)
		if !ok {
			respError(w, 404, "experiment not found")
			return
		}
		respJSON(w, 200, exp)
	})

	// Run experiment
	mux.HandleFunc("/api/experiments/{id}/run", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			respError(w, 405, "method not allowed")
			return
		}
		id := r.PathValue("id")
		exp, ok := experiments.FindByID(id)
		if !ok {
			respError(w, 404, "experiment not found")
			return
		}

		var params map[string]any
		if err := json.NewDecoder(r.Body).Decode(&params); err != nil {
			respError(w, 400, "invalid json: "+err.Error())
			return
		}

		outputDir := filepath.Join("hcp-lab", "hcp-lab-server", "data", "results", id+"_"+strconv.FormatInt(time.Now().UnixNano(), 10))
		task, err := st.CreateTask(id, exp.Name, params, outputDir)
		if err != nil {
			respError(w, 500, "create task: "+err.Error())
			return
		}

		if err := rnr.Start(task, *exp); err != nil {
			respError(w, 500, "start task: "+err.Error())
			return
		}

		respJSON(w, 200, task)
	})

	// AI: Generate experiment
	mux.HandleFunc("/api/ai/generate", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			respError(w, 405, "method not allowed")
			return
		}

		var req ai.ExperimentRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			respError(w, 400, "invalid json: "+err.Error())
			return
		}

		exp, err := aiSvc.GenerateExperiment(req)
		if err != nil {
			respError(w, 500, "generate experiment: "+err.Error())
			return
		}

		respJSON(w, 200, exp)
	})

	// AI: Get config
	mux.HandleFunc("/api/ai/config", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			respJSON(w, 200, aiSvc.GetConfig())
		} else if r.Method == http.MethodPut {
			var config ai.AIConfig
			if err := json.NewDecoder(r.Body).Decode(&config); err != nil {
				respError(w, 400, "invalid json: "+err.Error())
				return
			}
			if err := aiSvc.UpdateConfig(config); err != nil {
				respError(w, 500, "update config: "+err.Error())
				return
			}
			respJSON(w, 200, map[string]bool{"updated": true})
		} else {
			respError(w, 405, "method not allowed")
		}
	})

	// AI: Test config
	mux.HandleFunc("/api/ai/test", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			respError(w, 405, "method not allowed")
			return
		}

		var config ai.AIConfig
		if err := json.NewDecoder(r.Body).Decode(&config); err != nil {
			respError(w, 400, "invalid json: "+err.Error())
			return
		}

		// Test the AI configuration
		testReq := map[string]any{
			"model": config.Model,
			"messages": []map[string]string{
				{
					"role":    "user",
					"content": "Hello, please respond with 'OK' if you receive this message.",
				},
			},
			"max_tokens": 10,
		}

		body, err := json.Marshal(testReq)
		if err != nil {
			respError(w, 500, "marshal request: "+err.Error())
			return
		}

		httpReq, err := http.NewRequest("POST", config.APIURL, bytes.NewBuffer(body))
		if err != nil {
			respError(w, 500, "create request: "+err.Error())
			return
		}

		httpReq.Header.Set("Content-Type", "application/json")
		httpReq.Header.Set("Authorization", "Bearer "+config.APIKey)

		client := &http.Client{
			Timeout: 30 * time.Second,
		}

		resp, err := client.Do(httpReq)
		if err != nil {
			respError(w, 500, "connection failed: "+err.Error())
			return
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			respError(w, resp.StatusCode, "API returned error: "+resp.Status)
			return
		}

		respJSON(w, 200, map[string]string{"status": "ok", "message": "AI API connection successful"})
	})

	// List tasks
	mux.HandleFunc("/api/tasks", func(w http.ResponseWriter, r *http.Request) {
		expID := r.URL.Query().Get("exp_id")
		tasks := st.ListTasks(expID)
		respJSON(w, 200, tasks)
	})

	// Get task
	mux.HandleFunc("/api/tasks/{id}", func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")
		task, ok := st.GetTask(id)
		if !ok {
			respError(w, 404, "task not found")
			return
		}
		respJSON(w, 200, task)
	})

	// Delete task
	mux.HandleFunc("/api/tasks/{id}/delete", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost && r.Method != http.MethodDelete {
			respError(w, 405, "method not allowed")
			return
		}
		id := r.PathValue("id")
		if err := st.DeleteTask(id); err != nil {
			respError(w, 500, err.Error())
			return
		}
		respJSON(w, 200, map[string]bool{"deleted": true})
	})

	// Get result file
	mux.HandleFunc("/api/tasks/{id}/results/", func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")
		task, ok := st.GetTask(id)
		if !ok {
			respError(w, 404, "task not found")
			return
		}
		filePath := strings.TrimPrefix(r.URL.Path, "/api/tasks/"+id+"/results/")
		if filePath == "" {
			respError(w, 400, "missing file path")
			return
		}
		// Security: prevent directory traversal
		filePath = filepath.Clean(filePath)
		if strings.Contains(filePath, "..") {
			respError(w, 400, "invalid file path")
			return
		}
		fullPath := filepath.Join(task.OutputDir, filePath)
		// Ensure it's within outputDir
		if !strings.HasPrefix(fullPath, filepath.Clean(task.OutputDir)) {
			respError(w, 400, "invalid file path")
			return
		}
		data, err := os.ReadFile(fullPath)
		if err != nil {
			respError(w, 404, "file not found")
			return
		}
		// Set content type based on extension
		if strings.HasSuffix(filePath, ".json") {
			w.Header().Set("Content-Type", "application/json")
		} else if strings.HasSuffix(filePath, ".svg") {
			w.Header().Set("Content-Type", "image/svg+xml")
		} else if strings.HasSuffix(filePath, ".md") {
			w.Header().Set("Content-Type", "text/markdown")
		} else {
			w.Header().Set("Content-Type", "application/octet-stream")
		}
		w.Write(data)
	})

	// WebSocket
	mux.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		ws.ServeWS(hub, w, r)
	})

	addr := ":" + *port
	log.Printf("hcp-lab-server listening on %s, project root: %s", addr, absRoot)
	if err := http.ListenAndServe(addr, enableCORS(mux)); err != nil {
		log.Fatal(err)
	}
}
