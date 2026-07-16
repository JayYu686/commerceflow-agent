package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func testLauncher(t *testing.T, runner commandRunner) *launcher {
	t.Helper()
	return &launcher{
		run:         runner,
		dataDir:     t.TempDir(),
		version:     "v1.0.0",
		projectName: "commerceflow-agent-demo",
		healthURL:   "http://127.0.0.1:1/health",
		consoleURL:  "http://localhost:3000",
		openBrowser: func(string) error { return nil },
		portFree:    func(int) bool { return true },
		waitDelay:   time.Millisecond,
		waitLimit:   time.Millisecond,
	}
}

func TestEnsureComposeWritesEmbeddedReleaseFile(t *testing.T) {
	app := testLauncher(t, func(string, ...string) (string, error) { return "", nil })

	if err := app.ensureCompose(); err != nil {
		t.Fatal(err)
	}
	content, err := os.ReadFile(filepath.Join(app.dataDir, "compose.demo.yml"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(content), "commerceflow-agent-api") {
		t.Fatal("embedded compose file does not contain the API image")
	}
}

func TestComposeArgsPinProjectAndFile(t *testing.T) {
	app := testLauncher(t, func(string, ...string) (string, error) { return "", nil })
	args := strings.Join(app.composeArgs("up", "-d"), " ")

	if !strings.Contains(args, "-p commerceflow-agent-demo") {
		t.Fatalf("project name missing from compose args: %s", args)
	}
	if !strings.Contains(args, "compose.demo.yml up -d") {
		t.Fatalf("compose path or command missing: %s", args)
	}
}

func TestStartRefusesOccupiedPortBeforePull(t *testing.T) {
	commands := []string{}
	app := testLauncher(t, func(name string, args ...string) (string, error) {
		commands = append(commands, name+" "+strings.Join(args, " "))
		return "", nil
	})
	app.portFree = func(port int) bool { return port != 3000 }

	err := app.start(false)
	if err == nil || !strings.Contains(err.Error(), "端口 3000") {
		t.Fatalf("expected occupied port error, got %v", err)
	}
	for _, command := range commands {
		if strings.Contains(command, " pull") {
			t.Fatalf("pull must not run after port conflict: %s", command)
		}
	}
}

func TestStopPreservesVolumes(t *testing.T) {
	commands := []string{}
	app := testLauncher(t, func(name string, args ...string) (string, error) {
		commands = append(commands, name+" "+strings.Join(args, " "))
		return "", nil
	})

	if err := app.stop(); err != nil {
		t.Fatal(err)
	}
	last := commands[len(commands)-1]
	if !strings.HasSuffix(last, " down") || strings.Contains(last, "-v") {
		t.Fatalf("stop must preserve volumes: %s", last)
	}
}

func TestResetRemovesVolumesOnlyWhenConfirmed(t *testing.T) {
	commands := []string{}
	app := testLauncher(t, func(name string, args ...string) (string, error) {
		commands = append(commands, name+" "+strings.Join(args, " "))
		if strings.Contains(strings.Join(args, " "), "ps --services") {
			return "api\nweb\n", nil
		}
		return "", nil
	})
	app.healthURL = ""
	app.waitLimit = 0

	err := app.reset(true)
	if err == nil || !strings.Contains(err.Error(), "API") {
		// The health wait is expected to fail after the destructive command in this unit test.
		t.Fatalf("expected health failure after reset, got %v", err)
	}
	found := false
	for _, command := range commands {
		if strings.HasSuffix(command, " down -v") {
			found = true
		}
	}
	if !found {
		t.Fatal("confirmed reset did not remove compose volumes")
	}
}
