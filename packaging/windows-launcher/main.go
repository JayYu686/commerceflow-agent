package main

import (
	"bufio"
	_ "embed"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

//go:embed compose.demo.yml
var composeFile []byte

//go:embed otel-collector-config.yaml
var collectorConfig []byte

var version = "v1.1.0"

type commandRunner func(name string, args ...string) (string, error)

type launcher struct {
	run         commandRunner
	dataDir     string
	version     string
	projectName string
	skipPull    bool
	observability bool
	healthURL   string
	consoleURL  string
	openBrowser func(string) error
	portFree    func(int) bool
	waitDelay   time.Duration
	waitLimit   time.Duration
}

func systemRunner(name string, args ...string) (string, error) {
	command := exec.Command(name, args...)
	command.Env = append(os.Environ(), "COMMERCEFLOW_VERSION="+version)
	output, err := command.CombinedOutput()
	if err != nil {
		return string(output), fmt.Errorf("command failed: %w", err)
	}
	return string(output), nil
}

func newLauncher() (*launcher, error) {
	localAppData := os.Getenv("LOCALAPPDATA")
	if localAppData == "" {
		return nil, errors.New("无法读取 LOCALAPPDATA，不能创建本地运行目录")
	}
	return &launcher{
		run:         systemRunner,
		dataDir:     filepath.Join(localAppData, "CommerceFlowAgent", version),
		version:     version,
		projectName: envOrDefault("COMMERCEFLOW_PROJECT_NAME", "commerceflow-agent-demo"),
		skipPull:    os.Getenv("COMMERCEFLOW_SKIP_PULL") == "1",
		healthURL:   "http://127.0.0.1:8000/health",
		consoleURL:  "http://localhost:3000",
		openBrowser: openBrowser,
		portFree:    portIsFree,
		waitDelay:   2 * time.Second,
		waitLimit:   3 * time.Minute,
	}, nil
}

func (app *launcher) composePath() string {
	return filepath.Join(app.dataDir, "compose.demo.yml")
}

func (app *launcher) composeArgs(arguments ...string) []string {
	base := []string{"compose", "-p", app.projectName, "-f", app.composePath()}
	if app.observability {
		base = append(base, "--profile", "observability")
	}
	return append(base, arguments...)
}

func (app *launcher) ensureCompose() error {
	if err := os.MkdirAll(app.dataDir, 0o755); err != nil {
		return fmt.Errorf("无法创建本地运行目录: %w", err)
	}
	if err := os.WriteFile(app.composePath(), composeFile, 0o644); err != nil {
		return fmt.Errorf("无法写入 Docker Compose 配置: %w", err)
	}
	collectorPath := filepath.Join(app.dataDir, "otel-collector-config.yaml")
	if err := os.WriteFile(collectorPath, collectorConfig, 0o644); err != nil {
		return fmt.Errorf("无法写入 OpenTelemetry Collector 配置: %w", err)
	}
	return nil
}

func (app *launcher) checkDocker() error {
	if _, err := app.run("docker", "compose", "version"); err != nil {
		return errors.New("未找到 Docker Compose，请安装并启动 Docker Desktop")
	}
	if _, err := app.run("docker", "version", "--format", "{{.Server.Version}}"); err != nil {
		return errors.New("Docker Desktop 尚未启动，请启动后重试")
	}
	return nil
}

func (app *launcher) projectRunning() bool {
	output, err := app.run("docker", app.composeArgs("ps", "--services", "--filter", "status=running")...)
	return err == nil && strings.Contains(output, "api") && strings.Contains(output, "web")
}

func (app *launcher) start(openConsole bool) error {
	if err := app.checkDocker(); err != nil {
		return err
	}
	if err := app.ensureCompose(); err != nil {
		return err
	}
	if !app.projectRunning() {
		ports := []int{3000, 8000}
		if app.observability {
			ports = append(ports, 4318, 16686)
			_ = os.Setenv("OTEL_ENABLED", "true")
		}
		for _, port := range ports {
			if !app.portFree(port) {
				return fmt.Errorf("端口 %d 已被其他程序占用，请释放端口后重试", port)
			}
		}
		if !app.skipPull {
			fmt.Println("正在拉取 CommerceFlow Agent 镜像...")
			if output, err := app.run("docker", app.composeArgs("pull")...); err != nil {
				return fmt.Errorf(
					"镜像拉取失败，请检查网络和 GHCR 镜像可见性: %s",
					safeOutput(output),
				)
			}
		}
		fmt.Println("正在启动本地演示环境...")
		if output, err := app.run("docker", app.composeArgs("up", "-d")...); err != nil {
			return fmt.Errorf("容器启动失败: %s", safeOutput(output))
		}
	}
	if err := app.waitForHealth(); err != nil {
		return err
	}
	fmt.Printf("系统已就绪：%s\n", app.consoleURL)
	if openConsole {
		return app.openBrowser(app.consoleURL)
	}
	return nil
}

func (app *launcher) waitForHealth() error {
	deadline := time.Now().Add(app.waitLimit)
	client := &http.Client{Timeout: 3 * time.Second}
	for time.Now().Before(deadline) {
		response, err := client.Get(app.healthURL)
		if err == nil {
			_ = response.Body.Close()
			if response.StatusCode == http.StatusOK {
				return nil
			}
		}
		time.Sleep(app.waitDelay)
	}
	return errors.New("API 在规定时间内未就绪，请运行 status 查看容器状态")
}

func (app *launcher) status() error {
	if err := app.checkDocker(); err != nil {
		return err
	}
	if err := app.ensureCompose(); err != nil {
		return err
	}
	output, err := app.run("docker", app.composeArgs("ps")...)
	if err != nil {
		return errors.New("无法读取容器状态")
	}
	fmt.Print(output)
	return nil
}

func (app *launcher) stop() error {
	if err := app.checkDocker(); err != nil {
		return err
	}
	if err := app.ensureCompose(); err != nil {
		return err
	}
	if output, err := app.run("docker", app.composeArgs("down")...); err != nil {
		return fmt.Errorf("停止失败: %s", safeOutput(output))
	}
	fmt.Println("系统已停止，本地演示数据已保留。")
	return nil
}

func (app *launcher) reset(confirmed bool) error {
	if !confirmed {
		reader := bufio.NewReader(os.Stdin)
		fmt.Print("此操作会删除全部本地演示数据。输入 RESET 继续：")
		answer, _ := reader.ReadString('\n')
		if strings.TrimSpace(answer) != "RESET" {
			return errors.New("已取消重置")
		}
	}
	if err := app.checkDocker(); err != nil {
		return err
	}
	if err := app.ensureCompose(); err != nil {
		return err
	}
	if output, err := app.run("docker", app.composeArgs("down", "-v")...); err != nil {
		return fmt.Errorf("重置失败: %s", safeOutput(output))
	}
	return app.start(true)
}

func portIsFree(port int) bool {
	listener, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
	if err != nil {
		return false
	}
	_ = listener.Close()
	return true
}

func openBrowser(url string) error {
	if os.Getenv("COMMERCEFLOW_NO_BROWSER") == "1" {
		return nil
	}
	if runtime.GOOS != "windows" {
		return nil
	}
	return exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
}

func safeOutput(output string) string {
	trimmed := strings.TrimSpace(output)
	if len(trimmed) > 300 {
		return trimmed[:300] + "..."
	}
	return trimmed
}

func envOrDefault(name string, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func printMenu() {
	fmt.Println("CommerceFlow Agent 本地演示启动器")
	fmt.Println("1. 启动系统并打开浏览器")
	fmt.Println("2. 启动系统并启用可观测性")
	fmt.Println("3. 查看系统状态")
	fmt.Println("4. 重新打开控制台")
	fmt.Println("5. 停止系统并保留数据")
	fmt.Println("6. 重置本地演示数据")
	fmt.Println("7. 退出")
}

func runInteractive(app *launcher) error {
	reader := bufio.NewReader(os.Stdin)
	for {
		printMenu()
		fmt.Print("请选择：")
		choice, _ := reader.ReadString('\n')
		switch strings.TrimSpace(choice) {
		case "1":
			return app.start(true)
		case "2":
			app.observability = true
			return app.start(true)
		case "3":
			return app.status()
		case "4":
			return app.openBrowser(app.consoleURL)
		case "5":
			return app.stop()
		case "6":
			return app.reset(false)
		case "7":
			return nil
		default:
			fmt.Println("请输入 1 到 7。")
		}
	}
}

func main() {
	app, err := newLauncher()
	if err == nil {
		if len(os.Args) == 1 {
			err = runInteractive(app)
		} else {
			switch os.Args[1] {
			case "start":
				app.observability = len(os.Args) > 2 && os.Args[2] == "--observability"
				err = app.start(true)
			case "status":
				err = app.status()
			case "stop":
				err = app.stop()
			case "reset":
				err = app.reset(len(os.Args) > 2 && os.Args[2] == "--yes")
			default:
				err = errors.New("未知命令，可用命令：start、status、stop、reset")
			}
		}
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误：%v\n", err)
		os.Exit(1)
	}
}
