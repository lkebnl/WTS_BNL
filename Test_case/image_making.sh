lsblk
# sudo umount /dev/sda* # check is it sda or other
sudo dd if=/dev/sda of=~/QSFP_Jack.img bs=4M status=progress conv=fsync
# gzip ~/QSFP_Jack.img