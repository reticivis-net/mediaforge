cd /
curl -s https://api.github.com/repos/libvips/libvips/releases/latest | grep -wo "\"https://github.com/libvips/libvips/releases/download/.*.tar.xz\"" | tr -d \'\" | wget -i -
mkdir vips
tar -xf vips*.tar.xz -C vips --strip-components 1
rm vips*.tar.xz
cd vips
meson setup build --libdir=lib --buildtype=release -Dintrospection=false
cd build
meson compile
meson install
ldconfig
cd /
rm -r vips