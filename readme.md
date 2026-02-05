# README.md - Dự án Tide App

## 📝 Mô tả

Dự án này là một ứng dụng Dockerized được xây dựng bằng Python, hỗ trợ triển khai tự động lên VPS thông qua GitHub Actions và Cloudflare Tunnel.

## 🏗️ Cấu trúc dự án

```
tide-app/
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CD Pipeline
├── .gitignore
├── Dockerfile                   # Docker image definition
├── docker-compose.yml          # Docker Compose configuration
├── main.py                     # Ứng dụng chính
├── main1.py                    # Module bổ sung
└── README.md                   # Tài liệu dự án
```

## 🚀 Bắt đầu

### Yêu cầu

- Docker & Docker Compose
- Python 3.x
- Git

### Cài đặt cục bộ

```bash
# Clone repository
git clone https://github.com/ngtrthanh/tide-app.git
cd tide-app

# Chạy với Docker
docker-compose up -d

# Hoặc chạy trực tiếp với Python
python main.py
```

### Truy cập ứng dụng

- **Cục bộ:** http://localhost:8000
- **Production:** https://tide-app.yourdomain.com (sau khi cấu hình Cloudflare Tunnel)

## 🐳 Docker Commands

```bash
# Build và chạy
docker-compose up -d --build

# Xem logs
docker-compose logs -f

# Dừng container
docker-compose down

# Xóa images không sử dụng
docker image prune -f
```

## 🔄 CI/CD Pipeline

### Triển khai tự động

Khi code được push lên nhánh `main`, GitHub Actions sẽ tự động:

1. Checkout code
2. Build Docker image
3. Deploy lên VPS
4. Restart Cloudflare Tunnel

### Triển khai thủ công

```bash
# Trigger từ local
git add .
git commit -m "Mô tả thay đổi"
git push origin main
```

## ☁️ Cấu hình Cloudflare Tunnel

```bash
# Cài đặt cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Đăng nhập
cloudflared tunnel login

# Tạo tunnel
cloudflared tunnel create tide-app

# Cấu hình DNS
cloudflared tunnel route dns tide-app tide-app.yourdomain.com

# Chạy như service
cloudflared tunnel --config /root/.cloudflared/config.yml run
```

## 🔧 Cấu hình GitHub Secrets

Vào **Repository Settings** → **Secrets and variables** → **Actions**, thêm:

| Secret | Mô tả |
|--------|-------|
| `VPS_HOST` | Địa chỉ IP VPS |
| `VPS_USER` | Username SSH (root/ubuntu) |
| `VPS_SSH_KEY` | Private SSH key |
| `DOCKER_USERNAME` | Docker Hub username |
| `DOCKER_PASSWORD` | Docker Hub password |

## 📦 Phiên bản

- **Current:** v0.1.1
- **Release:** [GitHub Releases](https://github.com/ngtrthanh/tide-app/releases)

### Tạo phiên bản mới

```bash
git tag -a v0.1.2 -m "Release v0.1.2"
git push origin v0.1.2
```

## 🛡️ Bảo mật

- ✅ Sử dụng Cloudflare Tunnel thay vì mở port trực tiếp
- ✅ SSH key thay vì password
- ✅ GitHub Actions secrets cho credentials
- ✅ Docker containers isolated

## 📄 License

MIT License - Xem file LICENSE để biết thêm chi tiết.

## 📧 Liên hệ

- **GitHub:** [@ngtrthanh](https://github.com/ngtrthanh)
- **Repository:** https://github.com/ngtrthanh/tide-app