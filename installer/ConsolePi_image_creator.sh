#!/usr/bin/env bash

# --                                               ConsolePi Image Creation Script - Use at own Risk                                                         
# --  Wade Wells - Jan, 8 2019                                                                                                                     
# --    !!! USE @ own risk - This could bork your system !!!                                                                                           
# --                                                                                                                                             
# --  This is a script I used to expedite testing.  It looks for a raspbian-lite image file in whatever directory you run the script from, if it doesn't find one
# --  it downloads the latest image.  It will guesses what drive is the micro-sd card (the last USB device as I was using a USB to micro-sd adapter) then flashes 
# --  the raspbian-lite image to the micro-sd.
# --  
# --  You do get the opportunity to review fdisk -l to ensure it's the correct drive, and you can override the drive the script selects.  Obviously if you
# --  were to select the wrong drive, you would wipe out anything on that drive.  So don't do that.
# --  
# --  To further expedite testing the script will look for the following and move them to the /home/pi directory
# --    ConsolePi.conf, ConsolePi.ovpn, ovpn_credentials
# --    
# --    The install script looks for these files in the home dir of whatever user your logged in with, and will pull them in.  So in the case of ConsolePi.conf it 
# --    will pre-configure the Configuration with your real values allowing you to bypass the data entry.  In the case of the openvpn files it moves them to the
# --    openvpn/client folder once it's installed.  The script only provides example ovpn files as the specifics would be dependent on how your openvpn server is 
# --    configured.
# --  
# --  To aid in headless installation the script will enable SSH and can configure a wlan_ssid.  With those options on first boot the raspberry pi will connect to
# --  the SSID, so all you need to do is determine the IP address assigned and initiate an SSH session.
# --    To enable the pre-configuration of an SSID, configure the parameters below with values appropriate for your system
# --  
# --  Lastly this script also configures one of the consolepi quick commands: 'consolepi-install'. This command
# --  is the same as the single command install command on the github.  btw that command is changed to 'consolepi-upgrade' during the install.
# --  
# --  This script should be ran on a Linux system, tested on raspbian (a different Raspberry pi), and Linux mint, should work for most debian/ubuntu variants
# --  To use this script enter command: (this is not pulled by git, this script needs to be pulled manually for updates just check the date on top)
# --    'curl -JLO https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/ConsolePi_image_creator.sh  && sudo chmod +x ConsolePi_image_creator.sh'
# --  Enter a micro-sd card
# --  'sudo ./ConsolePi_image_creator.sh' When you are ready to flash the image

# WLAN Pre-Configuration - change fist parameter to true and configure valid parameters for the remainder to pre-configure an SSID on the image
configure_wpa_supplicant=false
ssid='ExampleSSID'
psk='ChangeMe!!'
wlan_country="US"
priority=0

# This option Configures ConsolePi image to install on first boot automatically
auto_install=true

main() {
    clear
	! $configure_wpa_supplicant && echo "wlan configuration will not be applied to image, to apply WLAN configuration break out of the script & change params @ top of this script"
    my_usb=$(ls -l /dev/disk/by-path/*usb* |grep -v part | sed 's/.*\(...\)/\1/')

    echo -e "\n\n\033[1;32mConsolePi Image Creator$*\033[m \n\n"
    echo -e "Script has discovered USB flash device @ \033[1;32m ${my_usb} $*\033[m"
    read -p "Do you want to see fdisk details for all disks to verify? (y/n): " input
    if [[ ! -z $input ]]; then 
        ([ ${input,,} == 'y' ] || [ ${input,,} == 'yes' ]) && input=true || input=false
    else
        input=true
    fi
    if $input; then
    echo "Displaying fdisk -l output in 'less' press q to quit"
    sleep 3
    sudo fdisk -l | less
    fi

    echo -e "Press enter to accept \033[1;32m ${my_usb} $*\033[m as the destination drive or specify the correct device i.e. 'sdc'"
    read -p "Device to flash with image [${my_usb}]:" input
    [[ ! -z input ]] && my_usb=$input
	[[ -z $my_usb ]] && echo "Something went wrong no destination device selected... exiting" && exit 1
    #echo -e "This script is going to flash the drive \033[1;32m ${my_usb} $*\033[m with raspian image\n Ctrl-C now to abort or press Enter to Continue"
    #read
    # umount device if currently mounted
    go_umount=true
    while $go_umount; do
    mount_point=$(mount | tail -1 | grep "${my_usb}" | awk '{print $3}')
    [[ ! -z $mount_point ]] && sudo umount $mount_point && echo "un-mounting $mount_point" || go_umount=false
    done

    echo "getting image"
    retry=0
    img_file=$(ls -lc *raspbian*-lite.img 2>>/dev/null | awk '{print $9}')
    while [[ -z $img_file ]] ; do
            echo "no image found in $(pwd) downloading image from raspberrypi.org"
            # wget https://downloads.raspberrypi.org/raspbian_lite_latest
            curl -JLO https://downloads.raspberrypi.org/raspbian_lite_latest
            zip_file=$(ls -lc *raspbian*-lite.zip 2>>/dev/null | awk '{print $9}')
            unzip $zip_file
            img_file=$(ls -lc *raspbian-stretch-lite.zip 2>>/dev/null | awk '{print $9}')
            ((retry++))
            [[ -z $img_file ]] && [[ $retry > 2 ]] && echo "exceeded retries exitting " && exit 1
    done
    
    # Burn Raspian image to device (micro-sd)
    echo -e "\n\nLast chance to abort!! (ctrl+c)"
    echo "Press any key to burn ${img_file} to ${my_usb}" 
    read
    echo -e "Now Burning image ${img_file} to ${my_usb} standby...\n this takes a few minutes\n"
    sudo dd bs=4M if="${img_file}" of=/dev/${my_usb} conv=fsync status=progress && echo -e "\n\n\033[1;32mImage written to flash - no Errors$*\033[m\n\n" || 
        echo "\n\n\033[1;32mError occurred burning image $*\033[m\n\n"

    echo "Mounting boot to enable ssh"
    # Create some mount-points
    [[ ! -d /mnt/usb1 ]] && sudo mkdir /mnt/usb1 && usb1_existed=false
    [[ ! -d /mnt/usb2 ]] && sudo mkdir /mnt/usb2 && usb2_existed=false
    sudo mount /dev/${my_usb}1 /mnt/usb1 || exit 1
    echo "Configuring ssh to be enabled by default"
    sudo touch /mnt/usb1/ssh
    sudo umount /mnt/usb1

    echo -e "SSh is now enabled\n\nMounting System Drive"
    sudo mount /dev/${my_usb}2 /mnt/usb2
    
    #Configure simple psk SSID based on params in this script
    if $configure_wpa_supplicant; then
        echo -e "Configuring wpa_supplicant.conf | defining ${ssid}"
        sudo echo "country=${wlan_country}" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        sudo echo "network={" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        sudo echo "        ssid=\"${ssid}\"" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        sudo echo "        psk=\"${psk}\"" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        [[ $priority > 0 ]] && sudo echo "        priority=${priority}" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        sudo echo "}" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
    fi
   
    # first-boot script
    if $auto_install; then
        sudo echo "consolepi-install" >> /mnt/usb2/home/pi/.bashrc
    fi

    [[ ! -d /mnt/usb2/usr/local/bin ]] && sudo mkdir /mnt/usb2/usr/local/bin
    sudo echo '#!/usr/bin/env bash' > /mnt/usb2/usr/local/bin/consolepi-install
    sudo echo "sudo wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.sh -O /tmp/ConsolePi && sudo bash /tmp/ConsolePi && sudo rm -f /tmp/ConsolePi" \
          >> /mnt/usb2/usr/local/bin/consolepi-install

    sudo chmod +x /mnt/usb2/usr/local/bin/consolepi-install
    echo

    # Look for pre-configuration files in users home dir
    cur_dir=$(pwd)
    pi_home="/mnt/usb2/home/pi"
    [[ -f "${cur_dir}/ConsolePi.conf" ]] && cp "${cur_dir}/ConsolePi.conf" $pi_home  && echo "ConsolePi.conf found pre-staging on image"
    [[ -f "${cur_dir}/ConsolePi.ovpn" ]] && cp "${cur_dir}/ConsolePi.ovpn" $pi_home && echo "ConsolePi.ovpn found pre-staging on image"
    [[ -f "${cur_dir}/ovpn_credentials" ]] && cp "${cur_dir}/ovpn_credentials" $pi_home && echo "ovpn_credentials found pre-staging on image"
	
	# if wpa_supplicant.conf exist in script dir cp it to image extract EAP-TLS cert details and cp certs (not a loop only good to pre-configure 1)
	if [[ -f "${cur_dir}/wpa_supplicant.conf" ]]; then
        echo "wpa_supplicant.conf found pre-staging on image"
        sudo cp "${cur_dir}/wpa_supplicant.conf" /mnt/usb2/etc/wpa_supplicant
		sudo chown root /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf
		sudo chgrp root /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf
		sudo chmod 644 /mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf 
        client_cert=$(grep client_cert= wpa_supplicant.conf | cut -d'"' -f2| cut -d'"' -f1)
		if [[ ! -z $client_cert ]]; then
            cert_path="/mnt/usb2"${client_cert%/*}
            ca_cert=$(grep ca_cert= wpa_supplicant.conf | cut -d'"' -f2| cut -d'"' -f1)
			private_key=$(grep private_key= wpa_supplicant.conf | cut -d'"' -f2| cut -d'"' -f1)
			[[ -d cert ]] && cd cert	# if script dir contains cert subdir look there for certs - otherwise look in script dir
			[[ ! -d $cert_path ]] && sudo mkdir "${cert_path}" # Will only work if all but the final folder already exists - I don't need more so...
			[[ -f ${client_cert##*/} ]] && sudo cp ${client_cert##*/} "${cert_path}/${client_cert##*/}"
			[[ -f ${ca_cert##*/} ]] && sudo cp ${ca_cert##*/} "${cert_path}/${ca_cert##*/}"
			[[ -f ${private_key##*/} ]] && sudo cp ${private_key##*/} "${cert_path}/${private_key##*/}"
			cd "${cur_dir}"
		fi
	fi	

    sudo umount /mnt/usb2
    # Remove our mount_points if they didn't happen to already exist when the script started
    ! $usb1_existed && rmdir /mnt/usb1
    ! $usb2_existed && rmdir /mnt/usb2

    echo -e "\npi zero flash drive ready\n\n"
    echo "Boot RaspberryPi with this image, then enter 'consolepi-install' to deploy ConsolePi"
}


iam=`whoami`
if [ "${iam}" = "root" ]; then 
    main
else
    echo 'Script should be ran as root. exiting.'
fi