package runner

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"

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

// buildArgs converts params map to command line arguments.
func buildArgs(params map[string]any) []string {
	var args []string
	for k, v := range params {
		key := "--" + strings.ReplaceAll(k, "_", "-")
		var val string
		switch vv := v.(type) {
		case bool:
			if vv {
				args = append(args, key)
			} else {
				args = append(args, "--no-"+strings.ReplaceAll(k, "_", "-"))
			}
			continue
		case float64:
			val = strconv.FormatFloat(vv, 'f', -1, 64)
		case int:
			val = strconv.Itoa(vv)
		case string:
			val = vv
		default:
			val = fmt.Sprintf("%v", v)
		}
		args = append(args, key, val)
	}
	return args
}

// Start begins an experiment run asynchronously.
func (r *Runner) Start(ctx context.Context, task *store.Task, exp experiments.Experiment) error {
	scriptPath := experiments.ResolveScriptPath(r.projectRoot, exp.ScriptPath)

	// Ensure output dir exists and is absolute relative to project root
	outputDir := task.OutputDir
	if !filepath.IsAbs(outputDir) {
		outputDir = filepath.Join(r.projectRoot, outputDir)
	}
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return fmt.Errorf("mkdir output dir: %w", err)
	}

	args := buildArgs(task.Params)
	// Override out param to our task-specific dir
	args = overrideArg(args, "--out", outputDir)

	cmd := exec.CommandContext(ctx, "python3", append([]string{scriptPath}, args...)...)
	cmd.Dir = r.projectRoot
	cmd.Env = append(os.Environ(), "PYTHONPATH="+filepath.Join(r.projectRoot, "hcp-lab"))

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

func overrideArg(args []string, key, val string) []string {
	for i := 0; i < len(args); i++ {
		if args[i] == key && i+1 < len(args) {
			args[i+1] = val
			return args
		}
	}
	return append(args, key, val)
}

func (r *Runner) streamLogs(taskID string, stdout, stderr io.Reader) {
	scan := func(rd io.Reader) {
		scanner := bufio.NewScanner(rd)
		for scanner.Scan() {
			line := scanner.Text()
			r.hub.Broadcast(ws.Message{TaskID: taskID, Type: "log", Payload: line})
			// Try to parse progress from known patterns
			if strings.Contains(line, "进度") || strings.Contains(line, "progress") {
				// simplistic progress parsing: look for X/Y
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

func (r *Runner) collectResults(outputDir string) ([]string, map[string]any) {
	var files []string
	metrics := make(map[string]any)

	// Walk outputDir
	_ = filepath.Walk(outputDir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		rel, _ := filepath.Rel(outputDir, path)
		files = append(files, rel)

		// Parse result.json
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
	// For simplicity, we rely on context cancellation in future versions.
	return r.store.UpdateStatus(taskID, store.TaskStatusCancelled)
}

// GenerateMatrixID creates a unique output directory name for a task.
func GenerateMatrixID(expID string) string {
	return fmt.Sprintf("hcp-lab/hcp-lab-server/data/results/%s_%s", expID, time.Now().Format("20060102_150405"))
}
