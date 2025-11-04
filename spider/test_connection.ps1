# 测试SSH端口22连接
Write-Host "测试SSH端口22连接..." -ForegroundColor Yellow
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("47.121.133.201", 22)
    Write-Host "✅ SSH端口22连接成功" -ForegroundColor Green
    $tcp.Close()
} catch {
    Write-Host "❌ SSH端口22连接失败: $($_.Exception.Message)" -ForegroundColor Red
}

# 测试MySQL端口3306连接
Write-Host "`n测试MySQL端口3306连接..." -ForegroundColor Yellow
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("47.121.133.201", 3306)
    Write-Host "✅ MySQL端口3306连接成功" -ForegroundColor Green
    $tcp.Close()
} catch {
    Write-Host "❌ MySQL端口3306连接失败: $($_.Exception.Message)" -ForegroundColor Red
}

# 测试网络连通性
Write-Host "`n测试网络连通性..." -ForegroundColor Yellow
try {
    $ping = Test-Connection -ComputerName "47.121.133.201" -Count 1 -Quiet
    if ($ping) {
        Write-Host "✅ 网络连通性正常" -ForegroundColor Green
    } else {
        Write-Host "❌ 网络连通性异常" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ 网络连通性测试失败: $($_.Exception.Message)" -ForegroundColor Red
} 