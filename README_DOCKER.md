# 📚 智能图书整理与书架系统 - Docker 容器化部署指南

本项目已完整容器化，可在 **群晖 (Synology NAS)、威联通 (QNAP)、Unraid、TrueNAS、Linux 服务器及 Windows/macOS Docker Desktop** 上一键部署运行。

---

## 一、核心特性（Docker Web 版）

- **🖼️ Z-Library 风格海报流视觉书架**：
  - 自动呈现已整理书库的高清封面网格、青色圆角徽章与书籍信息；
  - 手机、平板（iPad）、电脑浏览器全端自适应响应式布局。
- **📖 浏览器内置在线阅读**：
  - 手机或电脑无需安装任何第三方阅读软件，在网页端点击 **“在线阅读”** 即可直接阅读 EPUB 与 TXT 章节正文。
- **⬇️ 随时随地下载与元数据管理**：
  - 支持一键将书库电子书下载至手机/电纸书；
  - 网页端直接修改书名、作者、出版社、ISBN、简介，并一键安全删除废弃图书。
- **⚙️ 网页端全自动图书整理引擎**：
  - 网页上一键启动 **“预演测试 (Dry-Run)”** 或 **“正式入库”**；
  - 集成**当当正版图书核心权威库**、豆瓣读书与谷歌图书，智能识别官方出版全集与拼凑合集，免 Key 自动填补 ISBN；
  - 实时动态显示任务百分比进度条、5 维数据统计卡片与彩色控制台日志；
  - 整理完成自动刷新书架数据。

---

## 二、快速启动方式

### 方式 A：Docker Compose 一键启动 (强烈推荐)

在项目根目录下已有 `docker-compose.yml`，只需根据您的实际路径修改挂载目录：

```yaml
version: '3.8'

services:
  book-organizer:
    image: book-organizer:latest
    build:
      context: .
      dockerfile: Dockerfile
    container_name: book-organizer
    restart: unless-stopped
    ports:
      - "14808:14808"
    environment:
      - TZ=Asia/Shanghai
      - PORT=14808
    volumes:
      # 待整理图书源目录 (宿主机实际路径 : 容器 /source)
      - /path/to/downloads/books:/source
      # 已整理标准书库目录 (宿主机实际路径 : 容器 /library)
      - /path/to/library/organized:/library
      # 配置文件与缓存持久化目录
      - ./config:/config
```

启动命令：
```bash
# 构建并后台运行
docker-compose up -d --build

# 查看运行日志
docker-compose logs -f
```

启动后，在局域网内任意设备的浏览器中打开：
👉 **`http://<您的NAS或服务器IP>:14808`** 即可直接使用！

---

### 方式 B：Docker 单行命令启动

```bash
# 1. 构建镜像
docker build -t book-organizer:latest .

# 2. 运行容器
docker run -d \
  --name book-organizer \
  --restart unless-stopped \
  -p 14808:14808 \
  -e TZ=Asia/Shanghai \
  -v /volume1/downloads/books:/source \
  -v /volume1/books/library:/library \
  -v /volume1/docker/book-organizer/config:/config \
  book-organizer:latest
```

---

## 三、群晖 (Synology) / Unraid / 威联通 图形化配置指南

### 1. 目录映射说明 (Volume Mapping)
容器内预设了 **3 个标准数据卷**：

| 容器内路径 | 宿主机/NAS 建议映射目录 | 说明 |
| :--- | :--- | :--- |
| **`/source`** | 您的未整理图书下载文件夹（如 `G:\epub合集` 或 `downloads/books`） | 存放待扫描整理的乱名电子书，支持只读/读写 |
| **`/library`** | 您的永久规范化书库（如 `D:\downloads\魏总的书库` 或 `books/library`） | 整理后的标准 Calibre 结构书库，也是画廊书架读取的目录 |
| **`/config`** | 任意空目录（如 `docker/book-organizer/config`） | 持久化保存 `settings.json` 设置，容器重启不丢配置 |

### 2. 端口设置 (Port)
- 容器端口：`14808`
- 本地端口：`14808`（若被占用，可改为如 `8888` 或 `8090`）

---

## 四、高级进阶：容器内命令行单次/定时整理

如果您希望通过 NAS 定时任务（如 crontab）在后台自动无人值守整理：

```bash
# 1. 单次执行自动整理 (采用复制模式)
docker exec -it book-organizer /app/entrypoint.sh organize --action copy

# 2. 单次执行自动整理 (采用移动模式)
docker exec -it book-organizer /app/entrypoint.sh organize --action move

# 3. 仅预演分析，输出统计报告而不移动文件
docker exec -it book-organizer /app/entrypoint.sh dry-run
```

---

## 五、发布镜像到 Docker Hub (Publish to Docker Hub)

如果您希望将本系统打包推送到 Docker Hub 供其他设备或公众随时免编译拉取，有以下三种便捷方式：

### 方式 1：Windows / Linux 自动化一键脚本 (最简便)

- **Windows 用户**：双击运行项目根目录下的 **`push_to_dockerhub.bat`**，按照屏幕提示输入 Docker Hub 用户名与密码，脚本将全自动完成 `docker login`、`build` 与 `push`。
- **Linux / NAS / Mac 用户**：在终端执行：
  ```bash
  chmod +x push_to_dockerhub.sh
  ./push_to_dockerhub.sh
  ```
  *(脚本内置 buildx 多架构编译支持，可一键同时打包 `linux/amd64` 与 `linux/arm64`)*

---

### 方式 2：标准 Docker 命令手动发布

将 `<your_username>` 替换为您在 [Docker Hub](https://hub.docker.com/) 注册的真实用户名：

```bash
# 1. 登录 Docker Hub (输入账号与密码或 Access Token)
docker login

# 2. 构建镜像并打标签
docker build -t <your_username>/book-organizer:latest -t <your_username>/book-organizer:v1.0.0 .

# 3. 推送发布至 Docker Hub
docker push <your_username>/book-organizer:latest
docker push <your_username>/book-organizer:v1.0.0
```

#### 多架构编译发布 (推荐，同时适配群晖x86与树莓派/Apple Silicon ARM)：
```bash
docker buildx create --name mybuilder --use
docker buildx build --platform linux/amd64,linux/arm64 \
  -t <your_username>/book-organizer:latest \
  -t <your_username>/book-organizer:v1.0.0 \
  --push .
```

---

### 方式 3：GitHub Actions 云端免本地环境全自动发布

项目内已包含 **`.github/workflows/docker-publish.yml`** 工作流：
1. 将本工程推送到您的 GitHub 仓库；
2. 在 GitHub 仓库设置：`Settings -> Secrets and variables -> Actions`，添加两条机密：
   - `DOCKERHUB_USERNAME`: 您的 Docker Hub 用户名；
   - `DOCKERHUB_TOKEN`: 您的 Docker Hub Access Token（在 Docker Hub 个人中心生成）；
3. 以后每次推送代码或发布 Release Tag（如 `v1.0.0`），GitHub 云端服务器将**全自动免费完成多架构构建并秒级发布到 Docker Hub**！
