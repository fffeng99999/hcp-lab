package ai

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"
)

// AIConfig holds the configuration for AI API.
type AIConfig struct {
	APIURL    string `json:"api_url"`
	APIKey    string `json:"api_key"`
	Model     string `json:"model"`
	Timeout   int    `json:"timeout"`
}

// ExperimentRequest represents the request to generate an experiment.
type ExperimentRequest struct {
	Name        string   `json:"name"`
	Description string   `json:"description"`
	Type        string   `json:"type"`
	Params      []string `json:"params"`
	Objectives  string   `json:"objectives"`
}

// GeneratedExperiment represents the AI-generated experiment.
type GeneratedExperiment struct {
	ID          string         `json:"id"`
	Name        string         `json:"name"`
	Description string         `json:"description"`
	Type        string         `json:"type"`
	Params      []ParamSchema  `json:"params"`
	CommonParams map[string]any `json:"common_params"`
	Metrics     []MetricDef    `json:"metrics"`
	Scripts     ExperimentScripts `json:"scripts"`
}

// ParamSchema defines a parameter for the experiment.
type ParamSchema struct {
	Name        string `json:"name"`
	Type        string `json:"type"`
	Default     any    `json:"default"`
	Description string `json:"description"`
	Required    bool   `json:"required"`
}

// MetricDef defines a metric for the experiment.
type MetricDef struct {
	Name        string `json:"name"`
	Description string `json:"description"`
	Unit        string `json:"unit"`
}

// ExperimentScripts defines the scripts for the experiment.
type ExperimentScripts struct {
	RunScript   string `json:"run_script"`
	TestScript  string `json:"test_script"`
	PythonScript string `json:"python_script"`
}

// Service handles AI experiment generation.
type Service struct {
	config AIConfig
	mu     sync.RWMutex
	rules  string
}

// NewService creates a new AI service.
func NewService(config AIConfig) (*Service, error) {
	rules, err := loadRules()
	if err != nil {
		return nil, fmt.Errorf("load rules: %w", err)
	}

	return &Service{
		config: config,
		rules:  rules,
	}, nil
}

// loadRules loads the experiment generation rules.
func loadRules() (string, error) {
	rulesPath := filepath.Join("internal", "ai", "rules.md")
	data, err := os.ReadFile(rulesPath)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// GenerateExperiment sends a request to AI to generate an experiment.
func (s *Service) GenerateExperiment(req ExperimentRequest) (*GeneratedExperiment, error) {
	prompt := s.buildPrompt(req)

	aiReq := map[string]any{
		"model": s.config.Model,
		"messages": []map[string]string{
			{
				"role":    "system",
				"content": "你是一个分布式系统实验生成专家。请严格按照规则生成实验配置，只返回JSON格式，不要包含任何其他文本。",
			},
			{
				"role":    "user",
				"content": prompt,
			},
		},
		"temperature": 0.3,
		"max_tokens":  4000,
	}

	body, err := json.Marshal(aiReq)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	httpReq, err := http.NewRequest("POST", s.config.APIURL, bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+s.config.APIKey)

	client := &http.Client{
		Timeout: time.Duration(s.config.Timeout) * time.Second,
	}

	resp, err := client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("send request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("AI API error: %s, body: %s", resp.Status, string(respBody))
	}

	var aiResp map[string]any
	if err := json.Unmarshal(respBody, &aiResp); err != nil {
		return nil, fmt.Errorf("parse response: %w", err)
	}

	// Extract content from AI response
	content, err := extractContent(aiResp)
	if err != nil {
		return nil, err
	}

	// Parse JSON from content
	var experiment GeneratedExperiment
	if err := json.Unmarshal([]byte(content), &experiment); err != nil {
		return nil, fmt.Errorf("parse experiment JSON: %w, content: %s", err, content)
	}

	// Validate experiment
	if err := s.validateExperiment(&experiment); err != nil {
		return nil, fmt.Errorf("validate experiment: %w", err)
	}

	return &experiment, nil
}

// buildPrompt builds the prompt for AI.
func (s *Service) buildPrompt(req ExperimentRequest) string {
	return fmt.Sprintf(`根据以下规则和要求，生成一个新的实验配置。

## 实验规则
%s

## 实验要求
- 实验名称: %s
- 实验描述: %s
- 实验类型: %s
- 实验参数: %s
- 实验目标: %s

请严格按照规则中的JSON格式返回实验配置，不要包含任何其他文本。确保：
1. 实验ID格式为 expX_name
2. 所有参数都有默认值
3. 脚本路径正确
4. 指标定义完整
5. 只返回JSON，不要包含markdown代码块标记`, s.rules, req.Name, req.Description, req.Type, strings.Join(req.Params, ", "), req.Objectives)
}

// extractContent extracts the content from AI response.
func extractContent(resp map[string]any) (string, error) {
	choices, ok := resp["choices"].([]any)
	if !ok || len(choices) == 0 {
		return "", fmt.Errorf("no choices in response")
	}

	firstChoice, ok := choices[0].(map[string]any)
	if !ok {
		return "", fmt.Errorf("invalid choice format")
	}

	message, ok := firstChoice["message"].(map[string]any)
	if !ok {
		return "", fmt.Errorf("invalid message format")
	}

	content, ok := message["content"].(string)
	if !ok {
		return "", fmt.Errorf("invalid content format")
	}

	// Remove markdown code blocks if present
	content = strings.TrimSpace(content)
	if strings.HasPrefix(content, "```json") {
		content = strings.TrimPrefix(content, "```json")
		content = strings.TrimSuffix(content, "```")
		content = strings.TrimSpace(content)
	} else if strings.HasPrefix(content, "```") {
		content = strings.TrimPrefix(content, "```")
		content = strings.TrimSuffix(content, "```")
		content = strings.TrimSpace(content)
	}

	return content, nil
}

// validateExperiment validates the generated experiment.
func (s *Service) validateExperiment(exp *GeneratedExperiment) error {
	if exp.ID == "" {
		return fmt.Errorf("experiment ID is required")
	}

	// Validate ID format
	if !regexp.MustCompile(`^exp\d+_[a-z0-9_]+$`).MatchString(exp.ID) {
		return fmt.Errorf("invalid experiment ID format: %s (expected: expX_name)", exp.ID)
	}

	if exp.Name == "" {
		return fmt.Errorf("experiment name is required")
	}

	if exp.Description == "" {
		return fmt.Errorf("experiment description is required")
	}

	// Validate params
	for _, param := range exp.Params {
		if param.Name == "" {
			return fmt.Errorf("parameter name is required")
		}
		if param.Type == "" {
			return fmt.Errorf("parameter type is required for %s", param.Name)
		}
		// Validate type
		validTypes := map[string]bool{
			"int": true, "float": true, "string": true, "bool": true, "list_int": true,
		}
		if !validTypes[param.Type] {
			return fmt.Errorf("invalid parameter type: %s for %s", param.Type, param.Name)
		}
	}

	return nil
}

// UpdateConfig updates the AI configuration.
func (s *Service) UpdateConfig(config AIConfig) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.config = config
	return nil
}

// GetConfig returns the current AI configuration.
func (s *Service) GetConfig() AIConfig {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.config
}
