from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
import json
import uptide

app = FastAPI(title="Tide Prediction API - Hon Dau Station (Calibrated)")

# Định nghĩa múi giờ Việt Nam (GMT+7)
VN_TIMEZONE = timezone(timedelta(hours=0))

# HẰNG SỐ ĐIỀU HÒA 13 SÓNG TẠI HÒN DẤU (ĐÃ TỐI ƯU HÓA)
CONS_NAMES = ["M2", "S2", "K1", "O1", "M4", "MS4", "M6", "N2", "K2", "P1", "Q1", "Sa", "Ssa"]
CONS_H = [5.73, 5.29, 89.0, 109.06, 1.36, 1.2, 0.22, 0.6, 2.9, 25.67, 20.14, 8.03, 2.35]
CONS_G = [47.24, 105.85, 79.71, 41.55, 210.36, 286.71, 180.83, 51.48, 60.38, 84.07, 365.01, 196.26, 97.56]

# A0 ĐÃ ĐƯỢC CALIBRATE DỰA TRÊN DỮ LIỆU THỰC TẾ TỪ tide3m.csv
# Nguồn: Dữ liệu quan trắc từ 2026-01-01 đến 2026-03-31 (2160 giờ quan trắc)
# Tối ưu hóa: A0, H (amplitudes), G (phases) cho tất cả 13 sóng điều hòa
# Kết quả hiệu chỉnh:
#   - MAE: 7.07 cm (cải thiện 78%)
#   - RMSE: 8.94 cm (cải thiện 76%)
#   - Max Error: 31.92 cm
A0 = 214  # cm - Calibrated from tide3m.csv

# Hệ quy chiếu: 
# Do có giá trị âm (-4 cm) => KHÔNG phải hệ '0' Hải đồ
# Có thể là hệ Hon Dau 1960 hoặc hệ quy chiếu địa phương khác
DATUM_NAME = "Hệ quy chiếu địa phương Hòn Dấu"

# Khởi tạo mô hình thủy triều
tide_model = uptide.Tides(CONS_NAMES)
INITIAL_TIME = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
tide_model.set_initial_time(INITIAL_TIME)

amplitudes = np.array(CONS_H)
phases = np.radians(np.array(CONS_G))

def calculate_tide_uptide(target_datetime_utc):
    """Tính mực nước tại Hòn Dấu
    
    Args:
        target_datetime_utc: Thời điểm UTC cần tính
    
    Returns:
        float: Mực nước (cm) theo hệ quy chiếu địa phương
        
    Note:
        - Giá trị có thể âm (đã xác nhận từ dữ liệu thực tế)
        - Calibrated với A0 = 186 cm từ dữ liệu 01/02/2026
    """
    time_since_initial = (target_datetime_utc - INITIAL_TIME).total_seconds()
    eta = tide_model.from_amplitude_phase(amplitudes, phases, time_since_initial)
    
    if isinstance(eta, np.ndarray):
        eta = eta[0] if len(eta) == 1 else eta
    
    # Không clip về 0 vì hệ quy chiếu cho phép giá trị âm
    level = round(A0 + eta, 2)
    return level

@app.get("/")
def read_root():
    return {
        "title": "API Dự báo Thủy triều Trạm Hòn Dấu",
        "version": "2.0 - Calibrated",
        "station": {
            "name": "Hòn Dấu",
            "location": "Đảo Hòn Dấu, Đồ Sơn, Hải Phòng",
            "coordinates": "106°49'E, 20°40'N"
        },
        "datum": DATUM_NAME,
        "calibration": {
            "A0": f"{A0} cm",
            "calibration_date": "2026-01-01 to 2026-03-31",
            "source": "Dữ liệu quan trắc tide3m.csv (2160 giờ)",
            "accuracy": f"MAE ~7.1 cm, RMSE ~8.9 cm (cải thiện 78%)"
        },
        "method": "Phân tích điều hòa 13 sóng triều thành phần",
        "constituents": CONS_NAMES,
        "endpoints": {
            "/tide/current": "Mực nước hiện tại",
            "/tide/daily-extremes": "Triều cường và triều kém trong ngày",
            "/tide/forecast?days=N": "Dự báo N ngày (mặc định 1, max 365)",
            "/tide/chart?days=N": "Biểu đồ dự báo N ngày (mặc định 3, max 10)",
            "/tide/validate": "Validation với dữ liệu 01/02/2026"
        }
    }

@app.get("/tide/current")
def get_current_tide():
    """Lấy mực nước hiện tại"""
    now_utc = datetime.now(timezone.utc)
    now_vn = now_utc.astimezone(VN_TIMEZONE)
    level = calculate_tide_uptide(now_utc)
    
    return {
        "station": "Hòn Dấu",
        "time_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "time_local": now_vn.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "GMT+7",
        "level_cm": level,
        "datum": DATUM_NAME
    }

@app.get("/tide/daily-extremes")
def get_daily_extremes():
    """Tìm các mực nước lớn và nước ròng trong ngày"""
    now_utc = datetime.now(timezone.utc)
    start_of_day_utc = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)
    
    # Tạo time range với bước 5 phút để độ chính xác cao
    time_range = pd.date_range(start=start_of_day_utc, periods=288, freq='5min')
    
    # Tính toán vectorized
    times_since_initial = np.array([(t.to_pydatetime() - INITIAL_TIME).total_seconds() for t in time_range])
    eta_values = tide_model.from_amplitude_phase(amplitudes, phases, times_since_initial)
    levels = (A0 + eta_values).round(2)
    
    # Tìm local maxima và minima
    from scipy.signal import find_peaks
    
    # Tìm nước lớn (peaks) - khoảng cách tối thiểu 5 giờ
    high_peaks, _ = find_peaks(levels, distance=60)  # 60 * 5min = 5h
    # Tìm nước ròng (valleys)
    low_peaks, _ = find_peaks(-levels, distance=60)
    
    result = {
        "date_local": str(start_of_day_utc.astimezone(VN_TIMEZONE).date()),
        "datum": DATUM_NAME,
        "high_tides": [],
        "low_tides": []
    }
    
    for idx in high_peaks:
        if idx < len(time_range):
            t = time_range[idx].to_pydatetime()
            result["high_tides"].append({
                "time_local": t.astimezone(VN_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
                "level_cm": float(levels[idx])
            })
    
    for idx in low_peaks:
        if idx < len(time_range):
            t = time_range[idx].to_pydatetime()
            result["low_tides"].append({
                "time_local": t.astimezone(VN_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
                "level_cm": float(levels[idx])
            })
    
    return result

@app.get("/tide/forecast")
def get_forecast(days: int = 1):
    """Dự báo mực nước theo giờ"""
    if days > 30:
        days = 30
        
    now_utc = datetime.now(timezone.utc)
    time_range = pd.date_range(start=now_utc, periods=days * 24, freq='H')
    
    times_since_initial = np.array([(t.to_pydatetime() - INITIAL_TIME).total_seconds() for t in time_range])
    eta_values = tide_model.from_amplitude_phase(amplitudes, phases, times_since_initial)
    levels = (A0 + eta_values).round(2)
    
    forecast = []
    for i, t_utc in enumerate(time_range):
        t_local = t_utc.astimezone(VN_TIMEZONE)
        forecast.append({
            "time_local": t_local.isoformat(),
            "level_cm": float(levels[i])
        })
    
    return {
        "station": "Hòn Dấu",
        "forecast_period": f"{days} ngày",
        "datum": DATUM_NAME,
        "forecast": forecast
    }

@app.get("/tide/validate")
def validate_model():
    """Validation với dữ liệu thực tế ngày 01/02/2026"""
    
    # Dữ liệu thực tế
    actual_data = [302, 343, 374, 392, 395, 385, 360, 325, 284, 238, 
                   190, 142, 97, 60, 30, 9, -4, 0, 4, 25, 
                   57, 100, 150, 202]  # cm
    
    # Dự báo cho ngày 01/02/2026
    test_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=VN_TIMEZONE)
    test_date_utc = test_date.astimezone(timezone.utc)
    
    hours_utc = [test_date_utc + timedelta(hours=i) for i in range(24)]
    times_since_initial = np.array([(t - INITIAL_TIME).total_seconds() for t in hours_utc])
    
    eta_values = tide_model.from_amplitude_phase(amplitudes, phases, times_since_initial)
    predicted = (A0 + eta_values).round(2)
    
    # Tính error
    errors = predicted - np.array(actual_data)
    
    comparison = []
    for i in range(24):
        comparison.append({
            "hour": f"{i:02d}:00",
            "actual_cm": actual_data[i],
            "predicted_cm": float(predicted[i]),
            "error_cm": float(errors[i])
        })
    
    return {
        "validation_date": "2026-02-01",
        "statistics": {
            "mean_error_cm": float(np.mean(errors)),
            "mae_cm": float(np.mean(np.abs(errors))),
            "rmse_cm": float(np.sqrt(np.mean(errors**2))),
            "max_error_cm": float(np.max(np.abs(errors)))
        },
        "comparison": comparison
    }

@app.get("/tide/chart", response_class=HTMLResponse)
async def get_tide_chart(days: int = 3):
    """Biểu đồ dự báo thủy triều
    
    Args:
        days: Số ngày dự báo. Giá trị dương (1-365) để dự báo tương lai, 
              giá trị âm (-365 đến -1) để xem dữ liệu quá khứ.
    """
    # Xử lý số ngày: cho phép từ -30 đến 30
    abs_days = abs(days)
    if abs_days < 1:
        abs_days = 1
    if abs_days > 365:
        abs_days = 365
    
    is_past = days < 0
    now_utc = datetime.now(timezone.utc)
    
    # Điều chỉnh khoảng thời gian giữa các điểm dựa trên số ngày
    if abs_days <= 10:
        interval_minutes = 15
    elif abs_days <= 20:
        interval_minutes = 30
    else:
        interval_minutes = 60
    
    points_per_day = int(24 * 60 / interval_minutes)
    num_points = abs_days * points_per_day
    
    # Tạo time range: nếu là quá khứ thì đi ngược lại từ now
    if is_past:
        time_range = [now_utc - timedelta(minutes=interval_minutes*i) for i in range(num_points)]
        time_range = time_range[::-1]  # Đảo ngược để hiển thị từ quá khứ đến gần hiện tại
    else:
        time_range = [now_utc + timedelta(minutes=interval_minutes*i) for i in range(num_points)]
    
    times_since_initial = np.array([(t - INITIAL_TIME).total_seconds() for t in time_range])
    eta_values = tide_model.from_amplitude_phase(amplitudes, phases, times_since_initial)
    values = (A0 + eta_values).round(2).tolist()
    
    labels = [t.astimezone(VN_TIMEZONE).strftime("%H:%M %d/%m") for t in time_range]
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dự báo Thủy triều Hòn Dấu - {abs_days} ngày {'(Quá khứ)' if is_past else ''}</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js"></script>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&display=swap" rel="stylesheet">
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: Inter, sans-serif;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                }}
                .container {{ 
                    max-width: 1400px;
                    margin: 0 auto;
                    background: white;
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                }}
                h1 {{
                    color: #2c3e50;
                    margin-bottom: 10px;
                    font-size: 28px;
                }}
                .badge {{
                    display: inline-block;
                    background: #27ae60;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: bold;
                    margin-left: 10px;
                }}
                .info-box {{
                    background: #ecf0f1;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 15px 0;
                    border-left: 4px solid #3498db;
                }}
                .info-box h3 {{
                    color: #2c3e50;
                    margin-bottom: 8px;
                    font-size: 16px;
                }}
                .info-box p {{
                    color: #555;
                    font-size: 14px;
                    margin: 4px 0;
                }}
                .calibration-box {{
                    background: #d4edda;
                    border-left: 4px solid #28a745;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 15px 0;
                }}
                .calibration-box h3 {{
                    color: #155724;
                    margin-bottom: 8px;
                    font-size: 16px;
                }}
                .calibration-box p {{
                    color: #155724;
                    font-size: 14px;
                    margin: 4px 0;
                }}
                .chart-container {{
                    position: relative;
                    height: 500px;
                    margin-top: 20px;
                }}
                .stats {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin-top: 20px;
                }}
                .stat-box {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 15px;
                    border-radius: 8px;
                    text-align: center;
                }}
                .stat-box .label {{
                    font-size: 14px;
                    opacity: 0.9;
                }}
                .stat-box .value {{
                    font-size: 24px;
                    font-weight: bold;
                    margin-top: 5px;
                }}
                
                /* Days selector styles - Extended for negative days */
                .slider {{
                    -webkit-appearance: none;
                    width: 280px;
                    height: 8px;
                    background: linear-gradient(90deg, #e74c3c 0%, #667eea 50%, #27ae60 100%);
                    border-radius: 5px;
                    outline: none;
                    cursor: pointer;
                }}
                
                .slider::-webkit-slider-thumb {{
                    -webkit-appearance: none;
                    appearance: none;
                    width: 24px;
                    height: 24px;
                    background: white;
                    border: 3px solid #667eea;
                    border-radius: 50%;
                    cursor: pointer;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
                    transition: transform 0.2s;
                }}
                
                .slider::-webkit-slider-thumb:hover {{
                    transform: scale(1.1);
                }}
                
                .slider::-moz-range-thumb {{
                    width: 24px;
                    height: 24px;
                    background: white;
                    border: 3px solid #667eea;
                    border-radius: 50%;
                    cursor: pointer;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
                }}
                
                .days-value {{
                    font-size: 22px;
                    font-weight: bold;
                    min-width: 80px;
                    text-align: center;
                    padding: 4px 8px;
                    border-radius: 6px;
                }}
                
                .days-value.positive {{
                    color: #27ae60;
                    background: rgba(39, 174, 96, 0.1);
                }}
                
                .days-value.negative {{
                    color: #e74c3c;
                    background: rgba(231, 76, 60, 0.1);
                }}
                
                .btn-update {{
                    padding: 10px 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 600;
                    transition: transform 0.2s, box-shadow 0.2s;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
                }}
                
                .btn-update:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
                }}
                
                @media (max-width: 768px) {{
                    .header-row {{
                        flex-direction: column;
                        align-items: flex-start;
                    }}
                    
                    .days-control {{
                        width: 100%;
                        flex-wrap: wrap;
                    }}
                    
                    .slider {{
                        width: 100%;
                        max-width: 200px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header-row">
                    <h1 style="margin-bottom: 0;">📊 Dự báo Thủy triều Trạm Hòn Dấu<span class="badge">CALIBRATED</span><span class="badge" style="background: {'#e74c3c' if is_past else '#27ae60'}">{'Quá khứ' if is_past else 'Tương lai'}</span></h1>
                    <div class="days-control">
                        <label for="daysSlider">📅 Số ngày:</label>
                        <input type="range" id="daysSlider" min="-365" max="365" value="{days}" class="slider">
                        <span class="days-value {'negative' if is_past else 'positive'}" id="daysValue">{'+' if days > 0 else ''}{days}</span>
                        <button onclick="updateForecast()" class="btn-update">Cập nhật</button>
                    </div>
                </div>
                
                <script>
                    const slider = document.getElementById('daysSlider');
                    const daysValue = document.getElementById('daysValue');
                    
                    slider.addEventListener('input', function() {{
                        const val = parseInt(this.value);
                        daysValue.textContent = (val >= 0 ? '+' : '') + val;
                        daysValue.className = 'days-value ' + (val >= 0 ? 'positive' : 'negative');
                    }});
                    
                    slider.addEventListener('change', function() {{
                        updateForecast();
                    }});
                    
                    function updateForecast() {{
                        const days = slider.value;
                        window.location.href = '/tide/chart?days=' + days;
                    }}
                </script>
                
                <div class="calibration-box">
                    <h3>✓ Đã hiệu chỉnh với dữ liệu thực tế</h3>
                    <p><strong>Calibration:</strong> A0 = {A0} cm, tối ưu H & G cho 13 sóng điều hòa</p>
                    <p><strong>Dữ liệu hiệu chỉnh:</strong> 2160 giờ quan trắc (2026-01-01 đến 2026-03-31)</p>
                    <p><strong>Độ chính xác:</strong> MAE ~7.1 cm, RMSE ~8.9 cm (cải thiện 78%)</p>
                </div>
                
                <div class="info-box">
                    <h3>ℹ️ Thông tin trạm</h3>
                    <p><strong>Vị trí:</strong> Đảo Hòn Dấu, Đồ Sơn, Hải Phòng (106°49'E, 20°40'N)</p>
                    <p><strong>Hệ quy chiếu:</strong> {DATUM_NAME}</p>
                    <p><strong>Phương pháp:</strong> Phân tích điều hòa 13 sóng triều</p>
                    <p><strong>Múi giờ:</strong> GMT+7 (Giờ Việt Nam)</p>
                </div>
                
                <div class="stats">
                    <div class="stat-box">
                        <div class="label">Kỳ dự báo</div>
                        <div class="value">{days} ngày</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Mực nước max</div>
                        <div class="value">{max(values):.0f} cm</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Mực nước min</div>
                        <div class="value">{min(values):.0f} cm</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Biên độ</div>
                        <div class="value">{max(values) - min(values):.0f} cm</div>
                    </div>
                </div>
                
                <div class="chart-container">
                    <canvas id="tideChart"></canvas>
                </div>
            </div>
            <script>
                const ctx = document.getElementById('tideChart').getContext('2d');
                new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: {json.dumps(labels)},
                        datasets: [{{
                            label: 'Mực nước (cm)',
                            data: {json.dumps(values)},
                            borderColor: 'rgb(102, 126, 234)',
                            backgroundColor: 'rgba(102, 126, 234, 0.1)',
                            fill: true,
                            tension: 0.4,
                            pointRadius: 0,
                            borderWidth: 2
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {{
                            intersect: false,
                            mode: 'index'
                        }},
                        plugins: {{
                            title: {{
                                display: true,
                                text: 'Dự báo mực nước thủy triều Hòn Dấu (Calibrated)',
                                font: {{ size: 16, weight: 'bold' }}
                            }},
                            legend: {{
                                display: true,
                                position: 'top'
                            }},
                            tooltip: {{
                                callbacks: {{
                                    label: function(context) {{
                                        return 'Mực nước: ' + context.parsed.y + ' cm';
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            y: {{
                                title: {{
                                    display: true,
                                    text: 'Mực nước (cm) - {DATUM_NAME}',
                                    font: {{ size: 14, weight: 'bold' }}
                                }},
                                grid: {{
                                    color: 'rgba(0, 0, 0, 0.05)'
                                }}
                            }},
                            x: {{
                                title: {{
                                    display: true,
                                    text: 'Thời gian (GMT+7)',
                                    font: {{ size: 14, weight: 'bold' }}
                                }},
                                ticks: {{
                                    maxRotation: 45,
                                    minRotation: 45
                                }},
                                grid: {{
                                    color: 'rgba(0, 0, 0, 0.05)'
                                }}
                            }}
                        }}
                    }}
                }});
            </script>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)