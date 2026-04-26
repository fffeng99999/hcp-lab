package runner

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"

	"hcp-lab-server/internal/experiments"
	"hcp-lab-server/internal/store"
	"hcp-lab-server/internal/ws"
)

// Runner manages experiment execution.
type Runner struct {
	projectRoot string
	store       *store.Store
	hub         *ws.Hub
}

// New creates a new Runner.
func New(projectRoot string, st *store.Store, hub *ws.Hub) *Runner {
	return &Runner{
		projectRoot: projectRoot,
		store:       st,
		hub:         hub,
	}
}

// envVarName returns the uppercase param name as environment variable key.
func envVarName(paramName string) string {
	return paramName
}

// buildEnv converts params map to environment variable slice.
func buildEnv(baseEnv []string, params map[string]any) []string {
	env := make([]string, len(baseEnv))
	copy(env, baseEnv)
	for k, v := range params {
		key := envVarName(k)
		var val string
		switch vv := v.(type) {
		case bool:
			val = strconv.FormatBool(vv)
		case float64:
			val = strconv.FormatFloat(vv, 'f', -1, 64)
		case int:
			val = strconv.Itoa(vv)
		case string:
			val = vv
		default:
			val = fmt.Sprintf("%v", v)
		}
		env = append(env, key+"="+val)
	}
	return env
}

// Start begins an experiment run asynchronously.
func (r *Runner) Start(task *store.Task, exp experiments.Experiment) error {
	scriptPath := experiments.ResolveScriptPath(r.projectRoot, exp.RunScript)
	reportDir := filepath.Join(r.projectRoot, exp.ReportDir)

	outputDir := filepath.Join(r.projectRoot, "hcp-lab", "hcp-lab-server", "data", "results", task.ID)
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return fmt.Errorf("mkdir output dir: %w", err)
	}

	cmd := exec.Command("bash", scriptPath)
	cmd.Dir = r.projectRoot
	cmd.Env = buildEnv(os.Environ(), task.Params)

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("stdout pipe: %w", err)
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return fmt.Errorf("stderr pipe: %w", err)
	}

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("start cmd: %w", err)
	}

	r.store.UpdateStatus(task.ID, store.TaskStatusRunning)

	// Stream logs via WebSocket
	go r.streamLogs(task.ID, stdout, stderr)

	// Wait for completion
	go func() {
		err := cmd.Wait()
		if err != nil {
			r.store.SetError(task.ID, err.Error())
			r.hub.Broadcast(ws.Message{TaskID: task.ID, Type: "error", Payload: err.Error()})
			return
		}

		// Copy report dir to task output dir
		if err := copyDir(reportDir, outputDir); err != nil {
			// Report may not exist if experiment failed silently; don't treat as fatal
			fmt.Fprintf(os.Stderr, "copy report dir: %v\n", err)
		}

		// Collect result files
		files, metrics := r.collectResults(outputDir)
		if err := r.store.SetResult(task.ID, files, metrics); err != nil {
			r.store.SetError(task.ID, err.Error())
			return
		}
		r.hub.Broadcast(ws.Message{TaskID: task.ID, Type: "completed", Payload: "done"})
	}()

	return nil
}

func (r *Runner) streamLogs(taskID string, stdout, stderr io.Reader) {
	scan := func(rd io.Reader) {
		scanner := bufio.NewScanner(rd)
		for scanner.Scan() {
			line := scanner.Text()
			r.hub.Broadcast(ws.Message{TaskID: taskID, Type: "log", Payload: line})
			// Try to parse progress from known patterns
			if containsAny(line, "进度", "progress", "[进度", "Running") {
				var current, total int
				if _, err := fmt.Sscanf(line, "[进度 %d/%d]", &current, &total); err == nil && total > 0 {
					progress := current * 100 / total
					r.store.UpdateProgress(taskID, progress)
				}
			}
		}
	}
	go scan(stdout)
	go scan(stderr)
}

func containsAny(s string, subs ...string) bool {
	for _, sub := range subs {
		if contains(s, sub) {
			return true
		}
	}
	return false
}

func contains(s, sub string) bool {
	return len(s) >= len(sub) && (s == sub || len(sub) > 0 && indexOf(s, sub) >= 0)
}

func indexOf(s, sub string) int {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}

func (r *Runner) collectResults(outputDir string) ([]string, map[string]any) {
	var files []string
	metrics := make(map[string]any)

	_ = filepath.Walk(outputDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		rel, _ := filepath.Rel(outputDir, path)
		files = append(files, rel)

		if info.Name() == "result.json" {
			data, err := os.ReadFile(path)
			if err == nil {
				var result map[string]any
				if json.Unmarshal(data, &result) == nil {
					metrics = result
				}
			}
		}
		return nil
	})

	return files, metrics
}

// Cancel kills a running task (best effort).
func (r *Runner) Cancel(taskID string) error {
	return r.store.UpdateStatus(taskID, store.TaskStatusCancelled)
}

// copyDir recursively copies src directory to dst.
func copyDir(src, dst string) error {
	info, err := os.Stat(src)
	if err != nil {
		return err
	}
	if !info.IsDir() {
		return fmt.Errorf("src is not a directory: %s", src)
	}

	if err := os.MkdirAll(dst, info.Mode()); err != nil {
		return err
	}

	entries, err := os.ReadDir(src)
	if err != nil {
		return err
	}

	for _, entry := range entries {
		srcPath := filepath.Join(src, entry.Name())
		dstPath := filepath.Join(dst, entry.Name())

		if entry.IsDir() {
			if err := copyDir(srcPath, dstPath); err != nil {
				return err
			}
		} else {
			if err := copyFile(srcPath, dstPath); err != nil {
				return err
			}
		}
	}
	return nil
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, in)
	if err != nil {
		return err
	}
	return out.Close()
}
