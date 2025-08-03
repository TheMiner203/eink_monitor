sudo apt update
sudo apt install -y raspi-config python3-smbus python3-pip python3-pil
pip3 install psutil --break-system-packages
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_i2c 0
