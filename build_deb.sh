#!/bin/env bash
set -e

version=0.2

echo "building deb for wg_ips_calc $version"

if ! type "dpkg-deb" > /dev/null; then
  echo "please install required build tools first"
fi

echo "running core test"
python3 -m unittest test_wg_ips_core.py

project="wg-ips-calc_${version}_amd64"
folder_name="build/$project"
echo "crating $folder_name"
mkdir -p $folder_name
cp -r DEBIAN/ $folder_name
bin_dir="$folder_name/usr/bin"
lib_dir="$folder_name/usr/lib/wg_ips_calc"
res_dir="$lib_dir/resources"
mkdir -p $bin_dir
mkdir -p $lib_dir
mkdir -p $res_dir
cp wg-ips-calc $bin_dir
cp wg-ips-calc-cli $bin_dir
cp resources/icon.ico $res_dir
cp resources/icon.png $lib_dir
cp resources/wg-ips-calc.desktop $lib_dir
cp LICENSE $lib_dir
cp *.py $lib_dir

sed -i "s/_version_/$version/g" $folder_name/DEBIAN/control
cd build/ && dpkg-deb --build -Z gzip --root-owner-group $project
