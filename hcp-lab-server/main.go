package main

import (
	"encoding/json"
	"flag"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

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
