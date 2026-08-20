package settings

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
)

type AppSettings struct {
	UnpaywallEmail     string `json:"unpaywall_email"`
	InstitutionalProxy string `json:"institutional_proxy"`
	OutputDirectory    string `json:"output_directory"`
	VerifySSL          bool   `json:"verify_ssl"`
	UIMode             string `json:"ui_mode"`
}

type Manager struct {
	mu         sync.RWMutex
	configDir  string
	configFile string
	settings   AppSettings
}

func NewManager() (*Manager, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		home = "."
	}
	configDir := filepath.Join(home, ".litnexus")
	if err := os.MkdirAll(configDir, 0755); err != nil {
		return nil, err
	}

	configFile := filepath.Join(configDir, "settings.json")
	m := &Manager{
		configDir:  configDir,
		configFile: configFile,
		settings: AppSettings{
			VerifySSL:       true,
			OutputDirectory: filepath.Join(home, "Downloads", "LitNexus_PDFs"),
			UIMode:          "research",
		},
	}

	_ = m.Load()
	return m, nil
}

func (m *Manager) Load() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	data, err := os.ReadFile(m.configFile)
	if err != nil {
		return err
	}

	var s AppSettings
	if err := json.Unmarshal(data, &s); err != nil {
		return err
	}
	m.settings = s
	return nil
}

func (m *Manager) Save(s AppSettings) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}

	if err := os.WriteFile(m.configFile, data, 0644); err != nil {
		return err
	}
	m.settings = s
	return nil
}

func (m *Manager) GetSettings() AppSettings {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.settings
}
