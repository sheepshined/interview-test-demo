# DEMO3 本机启动手册

## 首次运行一次

### 1. 准备后端

```powershell
cd E:\hiagent\DEMO3\TOtal\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `.env`，填写：

```env
LLM_API_KEY=你的API密钥
```

构建题库：

```powershell
python main.py build
```

### 2. 准备前端

```powershell
cd E:\hiagent\DEMO3\TOtal\frontend
npm install
```

## 每次演示

打开两个 PowerShell 窗口。

### 窗口 1：后端

```powershell
cd E:\hiagent\DEMO3\TOtal\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 即启动成功。

若出现 `[WinError 10048]`，说明 `8000` 端口已被其他程序占用。先关闭旧后端或占用该端口的终端，再重新执行启动命令；可用 `netstat -ano | findstr :8000` 查看占用进程。

### 窗口 2：前端

```powershell
cd E:\hiagent\DEMO3\TOtal\frontend
npm run dev -- --host 127.0.0.1
```

浏览器打开：

```text
http://127.0.0.1:3000
```

登录账号：

```text
用户名：admin
密码：123123
```

## 快速检查

- 后端接口：`http://127.0.0.1:8000/api/roles`
- 接口文档：`http://127.0.0.1:8000/docs`
- 前端页面：`http://127.0.0.1:3000`

若岗位为空或简历请求失败，先确认 `/api/roles` 能返回 8 个岗位，再刷新前端页面。

关闭服务时，分别在两个 PowerShell 窗口按 `Ctrl + C`。
