"""Install published application updates without replacing the container image."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


IMAGE_DIR = Path(os.environ.get("BOOK_ORGANIZER_IMAGE_DIR", Path(__file__).resolve().parent))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/config"))
BASE_COMMIT = os.environ.get("BOOK_ORGANIZER_IMAGE_COMMIT", os.environ.get("GIT_COMMIT", ""))
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")
RESTART = 75
REPOSITORY = "https://github.com/a1139036147/book-organizer.git"
PUBLISHED_RUNS = (
    "https://api.github.com/repos/a1139036147/book-organizer/actions/workflows/"
    "docker-publish.yml/runs?branch=main&event=push&status=success&per_page=1"
)
MODULES = (
    "book_organizer.py", "bookshelf_manager.py", "calibre_shim.py", "config.py",
    "db_manager.py", "decoder.py", "epub_handler.py", "metadata_provider.py",
    "opf_generator.py", "plugins_manager.py", "version.py", "web_app.py",
)
IMAGE_ONLY = {
    "Dockerfile", ".dockerignore", "requirements.txt", "entrypoint.sh", "hot_update.py",
    "koodo-bookshelf.patch",
}


class UpdateError(Exception):
    pass


def supported():
    return CONFIG_DIR.is_dir() and bool(COMMIT_PATTERN.fullmatch(BASE_COMMIT))


def state_dir():
    return CONFIG_DIR / "hot-update" / BASE_COMMIT


def github_token():
    try:
        saved = (CONFIG_DIR / "github-token").read_text(encoding="utf-8").strip()
        if saved:
            return saved, "web"
    except FileNotFoundError:
        pass
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    return token, "environment" if token else "none"


def save_github_token(token):
    path = CONFIG_DIR / "github-token"
    if not token:
        path.unlink(missing_ok=True)
        return
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", token):
        raise ValueError("GitHub Token 格式无效。")
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=CONFIG_DIR, delete=False) as file:
            temporary = Path(file.name)
            file.write(token)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def latest_release():
    try:
        return github_release()
    except (URLError, TimeoutError, ValueError, KeyError, UpdateError):
        return docker_hub_release()


def github_release():
    request = Request(PUBLISHED_RUNS, headers={"Accept": "application/vnd.github+json"})
    token, _ = github_token()
    if token:
        request.add_unredirected_header("Authorization", f"Bearer {token}")
    with urlopen(request, timeout=10) as response:
        runs = json.load(response)["workflow_runs"]
    if not runs:
        raise UpdateError("GitHub 没有已成功发布的主分支构建。")
    run = runs[0]
    commit = run["head_sha"]
    version = f'2.6.{int(run["run_number"])}'
    if not COMMIT_PATTERN.fullmatch(commit):
        raise UpdateError("发布提交编号无效。")
    return {"commit": commit, "version": version, "build_date": run["created_at"]}


def docker_hub_release():
    repository = "arros/book-organizer"
    registry = f"https://registry-1.docker.io/v2/{repository}"
    with urlopen(
        f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repository}:pull",
        timeout=10,
    ) as response:
        token = json.load(response)["token"]

    def read(path, accept):
        request = Request(
            registry + path,
            headers={"Accept": accept},
        )
        request.add_unredirected_header("Authorization", f"Bearer {token}")
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    manifest_types = ", ".join((
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ))
    manifest = read("/manifests/latest", manifest_types)
    if "manifests" in manifest:
        platform = next((
            item for item in manifest["manifests"]
            if item.get("platform", {}).get("os") == "linux"
            and item.get("platform", {}).get("architecture") == "amd64"
        ), None)
        if not platform:
            raise UpdateError("Docker Hub 上的镜像缺少可识别的 Linux 构建。")
        manifest = read("/manifests/" + platform["digest"], manifest_types)
    image = read("/blobs/" + manifest["config"]["digest"], "application/octet-stream")
    env = dict(item.split("=", 1) for item in image["config"]["Env"] if "=" in item)
    commit, version = env.get("GIT_COMMIT", ""), env.get("APP_VERSION", "")
    if not COMMIT_PATTERN.fullmatch(commit) or not VERSION_PATTERN.fullmatch(version):
        raise UpdateError("Docker Hub 上的镜像缺少有效的版本或提交编号。")
    return {"commit": commit, "version": version, "build_date": env.get("BUILD_DATE", "")}


def has_update(release, current_commit, current_version):
    if release["commit"].startswith(current_commit) or not VERSION_PATTERN.fullmatch(current_version):
        return False
    return tuple(map(int, release["version"].split("."))) > tuple(map(int, current_version.split(".")))


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, timeout=60, capture_output=True,
    ).stdout


def install(release):
    if not supported():
        raise UpdateError("当前镜像缺少热更新所需的构建信息。")
    commit = release["commit"]
    if not COMMIT_PATTERN.fullmatch(commit):
        raise UpdateError("发布提交编号无效。")

    root = state_dir()
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=root) as temp:
        repo = Path(temp)
        git(repo, "init", "--quiet")
        git(repo, "fetch", "--quiet", "--depth=1", "--no-tags", REPOSITORY, BASE_COMMIT, commit)
        changed = git(repo, "diff", "--name-only", "-z", BASE_COMMIT, commit).decode().split("\0")
        if any(
            path in IMAGE_ONLY or path.startswith(("koodo_reader/", "calibre_plugins/")) or
            (path.endswith(".py") and "/" not in path and path not in MODULES)
            for path in changed
        ):
            raise UpdateError("该版本包含镜像层改动，请拉取新镜像升级。")

        staged = repo / "app"
        staged.mkdir()
        files = git(repo, "ls-tree", "-r", "-z", commit, "--", *MODULES, "templates/")
        for entry in files.split(b"\0"):
            if not entry:
                continue
            metadata, name = entry.decode().split("\t", 1)
            mode, kind, object_id = metadata.split()
            if mode not in ("100644", "100755") or kind != "blob" or ".." in Path(name).parts:
                raise UpdateError("更新包中存在不支持的文件。")
            path = staged / name
            path.parent.mkdir(parents=True, exist_ok=True)
            content = git(repo, "cat-file", "blob", object_id)
            if path.suffix == ".py":
                compile(content, name, "exec")
            path.write_bytes(content)

        if not (staged / "web_app.py").is_file():
            raise UpdateError("更新包缺少 Web 应用入口。")
        subprocess.run(
            [sys.executable, "-c", "import web_app; assert web_app.app.test_client().get('/').status_code == 200"],
            cwd=staged, env=release_env(release), check=True, timeout=20, capture_output=True,
        )
        destination = root / commit
        if not destination.exists():
            staged.replace(destination)
        marker = repo / "active.json"
        marker.write_text(json.dumps(release), encoding="utf-8")
        marker.replace(root / "active.json")


def release_env(release):
    return {
        **os.environ, "BOOK_ORGANIZER_IMAGE_DIR": str(IMAGE_DIR),
        "BOOK_ORGANIZER_IMAGE_COMMIT": BASE_COMMIT,
        "GIT_COMMIT": release["commit"], "APP_VERSION": release["version"],
        "BUILD_DATE": release["build_date"], "PYTHONPATH": str(IMAGE_DIR),
    }


def serve():
    marker = state_dir() / "active.json"
    child = None

    def stop(_signum, _frame):
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while True:
        root, env = IMAGE_DIR, None
        if supported() and marker.is_file():
            try:
                release = json.loads(marker.read_text(encoding="utf-8"))
                commit = release["commit"]
                if not COMMIT_PATTERN.fullmatch(commit):
                    raise ValueError("invalid commit")
                root = state_dir() / commit
                if not (root / "web_app.py").is_file():
                    raise ValueError("incomplete release")
                env = release_env(release)
            except (KeyError, TypeError, ValueError, OSError):
                root = IMAGE_DIR
                marker.unlink(missing_ok=True)
        started = time.monotonic()
        child = subprocess.Popen([sys.executable, str(root / "web_app.py")], cwd=IMAGE_DIR, env=env)
        if child.wait() == RESTART:
            continue
        if root != IMAGE_DIR and time.monotonic() - started < 10:
            marker.unlink(missing_ok=True)
            print("[hot-update] Web failed to start. Returning to the image version.", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    serve()
