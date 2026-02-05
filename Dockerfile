# Sử dụng slim Python image để tối giản và nhanh nhẹ
FROM python:3.11-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Cài đặt dependencies
RUN pip install --no-cache-dir fastapi uvicorn pandas numpy scipy uptide pytz

# Sao chép file mã nguồn
COPY main.py /app/main.py

# Expose cổng
EXPOSE 8000

# Chạy ứng dụng
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
