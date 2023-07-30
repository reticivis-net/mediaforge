cd /
mkdir magick
cd magick
wget https://imagemagick.org/archive/binaries/magick
chmod +x ./magick
./magick --appimage-extract
# evil hack to "install" app image
cp -rv ./squashfs-root/usr/* /usr
ldconfig
cd /
rm -r magick