## 💻 System monitor for Waveshare 2.13inch e-Paper display
![screenshot](https://github.com/TheMiner203/eink_monitor/blob/main/screenshot.png?raw=true)

# 📦 Hardware:
- [**Waveshare 2.13inch e-Paper HAT**](https://www.waveshare.com/wiki/2.13inch_e-Paper_HAT_Manual)
- [**UPS-Lite V1.3**](https://github.com/linshuqin329/UPS-Lite/) (optional)
- [**Raspberry Pi**](https://www.raspberrypi.com/) (tested on Zero W & Zero 2 W))

# ✨ Features:
- **Auto-shutdown at 0% battery**
- **Adaptive text rendering**
- **UPS Lite v1.3 support**
- **Automatic IP address detection**
- **Real-time updates every second**
- **Screen rotation support**

# 🛠️ Installation
1. Install git:
```bash
sudo apt install -y git
```
2. Clone the repository:
```bash
git clone https://github.com/TheMiner203/eink_monitor
cd eink_monitor
```
3. Install dependencies:
```bash
chmod +x ./install.sh
./install.sh
```
4. Run the application:
```bash
python3 eink_monitor.py &
```

## 📜 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

![Photo](https://github.com/TheMiner203/eink_monitor/blob/main/photo.jpg?raw=true)
