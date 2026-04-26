package runner

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

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

// buildEnv converts params map to environment variable slice.
func buildEnv(baseEnv []string, params map[string]any) []string {
	env := make([]string, len(baseEnv))
	copy(env, baseEnv)
	for k, v := range params {
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
		env = append(env, k+"="+val)
	}
	return env
}

// Start begins an experiment run asynchronously.
func (r *Runner) Start(task *store.Task, exp experiments.Experiment) error {
	scriptPath := experiments.ResolveScriptPath(r.projectRoot, exp.RunScript)

	if _, err := os.Stat(scriptPath); os.IsNotExist(err) {
		return fmt.Errorf("script not found: %s", scriptPath)
	}

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
	r.hub.Broadcast(ws.Message{TaskID: task.ID, Type: "started", Payload: "实验已启动"})

	go r.streamLogs(task.ID, stdout, stderr)

	go func() {
		err := cmd.Wait()
		if err != nil {
			errMsg := fmt.Sprintf("实验执行失败: %v", err)
			r.store.SetError(task.ID, errMsg)
			r.hub.Broadcast(ws.Message{TaskID: task.ID, Type: "error", Payload: errMsg})
			return
		}

		r.store.UpdateProgress(task.ID, 90)

		reportDir := filepath.Join(r.projectRoot, exp.ReportDir)
		if err := copyDir(reportDir, outputDir); err != nil {
			fmt.Fprintf(os.Stderr, "copy report dir (may not exist): %v\n", err)
		}

		files, metrics := r.collectResults(outputDir)
		if err := r.store.SetResult(task.ID, files, metrics); err != nil {
			r.store.SetError(task.ID, err.Error())
			return
		}

		r.store.UpdateProgress(task.ID, 100)
		r.hub.Broadcast(ws.Message{TaskID: task.ID, Type: "completed", Payload: "实验完成"})
	}()

	return nil
}

func (r *Runner) streamLogs(taskID string, stdout, stderr io.Reader) {
	progressPatterns := []*regexp.Regexp{
		regexp.MustCompile(`\[进度\s+(\d+)/(\d+)\]`),
		regexp.MustCompile(`progress:\s*(\d+)/(\d+)`),
		regexp.MustCompile(`(\d+)%\s*completed`),
		regexp.MustCompile(`\[EXP\]\s*(\d+)/(\d+)`),
	}

	scan := func(rd io.Reader) {
		scanner := bufio.NewScanner(rd)
		scanner.Buffer(make([]byte, 0, 64*1024), 256*1024)
		for scanner.Scan() {
			line := scanner.Text()
			r.hub.Broadcast(ws.Message{TaskID: taskID, Type: "log", Payload: line})

			for _, pattern := range progressPatterns {
				matches := pattern.FindStringSubmatch(line)
				if len(matches) == 3 {
					current, _ := strconv.Atoi(matches[1])
					total, _ := strconv.Atoi(matches[2])
					if total > 0 {
						progress := current * 100 / total
						r.store.UpdateProgress(taskID, progress)
						break
					}
				} else if len(matches) == 2 {
					percent, _ := strconv.Atoi(matches[1])
					if percent > 0 && percent <= 100 {
						r.store.UpdateProgress(taskID, percent)
						break
					}
				}
			}

			if strings.Contains(line, "Running") || strings.Contains(line, "开始实验") {
				r.store.UpdateProgress(taskID, 10)
			}
		}
	}
	go scan(stdout)
	go scan(stderr)
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

		baseName := info.Name()
		if baseName == "result.json" || baseName == "summary.json" {
			data, err := os.ReadFile(path)
			if err == nil {
				var result map[string]any
				if json.Unmarshal(data, &result) == nil {
					for k, v := range result {
						metrics[k] = v
					}
				}
			}
		}

		if strings.HasSuffix(baseName, ".csv") {
			metrics["csv_files"] = appendOrInit(metrics["csv_files"], rel)
		}

		if strings.HasSuffix(baseName, ".svg") {
			if count, ok := metrics["svg_count"].(int); ok {
				metrics["svg_count"] = count + 1
			} else {
				metrics["svg_count"] = 1
			}
		}

		return nil
	})

	if metrics["svg_count"] == nil {
		metrics["svg_count"] = 0
	}

	return files, metrics
}

func appendOrInit(existing any, item string) []string {
	if existing == nil {
		return []string{item}
	}
	if arr, ok := existing.([]string); ok {
		return append(arr, item)
	}
	return []string{item}
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
