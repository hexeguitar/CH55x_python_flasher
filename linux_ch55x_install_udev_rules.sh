#! /bin/bash
echo "Installing CH55x udev rules into /etc/udev/rules.d/"
sudo cp -i 99-ch55x.rules /etc/udev/rules.d/
echo "Restarting udev service..."
sudo service udev restart
echo "Reconnect the device"
