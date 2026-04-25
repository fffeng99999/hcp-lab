package store

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// TaskStatus represents the state of an experiment task.
type TaskStatus string

const (
	TaskStatusPending   TaskStatus = "pending"
	TaskStatusRunning   TaskStatus = "running"
	TaskStatusCompleted TaskStatus = "completed"
	TaskStatusFailed    TaskStatus = "failed"
	TaskStatusCancelled TaskStatus = "cancelled"
)

// Task represents a single experiment run.
type Task struct {
	ID          string                 `json:"id"`
	ExpID       string                 `json:"exp_id"`
	ExpName     string                 `json:"exp_name"`
	Status      TaskStatus             `json:"status"`
	Params      map[string]any         `json:"params"`
	OutputDir   string                 `json:"output_dir"`
	ResultFiles []string               `json:"result_files"`
	Metrics     map[string]any         `json:"metrics,omitempty"`
	ErrorMsg    string                 `json:"error_msg,omitempty"`
	CreatedAt   time.Time              `json:"created_at"`
	StartedAt   *time.Time             `json:"started_at,omitempty"`
	FinishedAt  *time.Time             `json:"finished_at,omitempty"`
	Progress    int                    `json:"progress"` // 0-100
}

// Store persists tasks to a JSON file.
type Store struct {
	mu       sync.RWMutex
	dataDir  string
	filePath string
	tasks    map[string]*Task
}

// New creates a new Store.
func New(dataDir string) (*Store, error) {
	if err := os.MkdirAll(dataDir, 0755); err != nil {
		return nil, err
	}
	s := &Store{
		dataDir:  dataDir,
		filePath: filepath.Join(dataDir, "tasks.json"),
		tasks:    make(map[string]*Task),
	}
	if err := s.load(); err != nil {
		// If file doesn't exist, start empty
		if !os.IsNotExist(err) {
			return nil, err
		}
	}
	return s, nil
}

func (s *Store) load() error {
	data, err := os.ReadFile(s.filePath)
	if err != nil {
		return err
	}
	var list []*Task
	if err := json.Unmarshal(data, &list); err != nil {
		return err
	}
	for _, t := range list {
		s.tasks[t.ID] = t
	}
	return nil
}

// save persists tasks to disk. Caller must hold s.mu (read or write lock).
func (s *Store) save() error {
	list := make([]*Task, 0, len(s.tasks))
	for _, t := range s.tasks {
		list = append(list, t)
	}

	data, err := json.MarshalIndent(list, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.filePath, data, 0644)
}

// CreateTask creates a new task and persists it.
func (s *Store) CreateTask(expID, expName string, params map[string]any, outputDir string) (*Task, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	task := &Task{
		ID:        fmt.Sprintf("%s_%d", expID, time.Now().UnixNano()),
		ExpID:     expID,
		ExpName:   expName,
		Status:    TaskStatusPending,
		Params:    params,
		OutputDir: outputDir,
		CreatedAt: time.Now(),
		Progress:  0,
	}
	s.tasks[task.ID] = task
	return task, s.save()
}

// GetTask retrieves a task by ID.
func (s *Store) GetTask(id string) (*Task, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	t, ok := s.tasks[id]
	return t, ok
}

// ListTasks returns all tasks, optionally filtered by expID.
func (s *Store) ListTasks(expID string) []*Task {
	s.mu.RLock()
	defer s.mu.RUnlock()

	list := make([]*Task, 0, len(s.tasks))
	for _, t := range s.tasks {
		if expID == "" || t.ExpID == expID {
			list = append(list, t)
		}
	}
	// Sort by created_at desc
	for i := 0; i < len(list)-1; i++ {
		for j := i + 1; j < len(list); j++ {
			if list[i].CreatedAt.Before(list[j].CreatedAt) {
				list[i], list[j] = list[j], list[i]
			}
		}
	}
	return list
}

// UpdateStatus updates the task status and persists.
func (s *Store) UpdateStatus(id string, status TaskStatus) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.tasks[id]
	if !ok {
		return fmt.Errorf("task not found: %s", id)
	}
	t.Status = status
	now := time.Now()
	if status == TaskStatusRunning {
		t.StartedAt = &now
	}
	if status == TaskStatusCompleted || status == TaskStatusFailed || status == TaskStatusCancelled {
		t.FinishedAt = &now
	}
	return s.save()
}

// UpdateProgress updates the task progress.
func (s *Store) UpdateProgress(id string, progress int) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.tasks[id]
	if !ok {
		return fmt.Errorf("task not found: %s", id)
	}
	if progress < 0 {
		progress = 0
	}
	if progress > 100 {
		progress = 100
	}
	t.Progress = progress
	return s.save()
}

// SetError sets the error message and marks failed.
func (s *Store) SetError(id string, errMsg string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.tasks[id]
	if !ok {
		return fmt.Errorf("task not found: %s", id)
	}
	t.Status = TaskStatusFailed
	t.ErrorMsg = errMsg
	now := time.Now()
	t.FinishedAt = &now
	return s.save()
}

// SetResult sets the result files and metrics.
func (s *Store) SetResult(id string, files []string, metrics map[string]any) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.tasks[id]
	if !ok {
		return fmt.Errorf("task not found: %s", id)
	}
	t.ResultFiles = files
	t.Metrics = metrics
	t.Status = TaskStatusCompleted
	now := time.Now()
	t.FinishedAt = &now
	t.Progress = 100
	return s.save()
}

// DeleteTask removes a task.
func (s *Store) DeleteTask(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.tasks, id)
	return s.save()
}
