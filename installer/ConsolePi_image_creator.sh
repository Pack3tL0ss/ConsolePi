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
# --  Enter a micro-sd card using a usb to micro-sd card adapter (script only works with usb to micro-sd adapters)
# --  'sudo ./ConsolePi_image_creator.sh' When you are ready to flash the image

# WLAN Pre-Configuration - change fist parameter to true and configure valid parameters for the remainder to pre-configure an SSID on the image
configure_wpa_supplicant=false
ssid='ExampleSSID'
psk='ChangeMe!!'
wlan_country="US"
priority=0

# This option Configures ConsolePi image to install on first boot automatically
auto_install=true

get_input() {
    valid_input=false
    while ! $valid_input; do
    read -p "${prompt} (y/n|exit): " input 
    case ${input,,} in
        'y'|'yes')
        input=true
        valid_input=true
        ;;
        'n'|'no')
        input=false
        valid_input=true
        ;;
        'exit')
        echo 'Exiting Script based on user input'
        exit 1
        ;;
        *)
        valid_input=false
        echo -e '\n\n!!! Invalid Input !!!\n\n'
        ;;
    esac
    done
    prompt=
}

do_unzip() {
    echo "Extracting image from ${1}"
    unzip $1
    img_file=$(ls -lc "${1%zip}.img" 2>>/dev/null | awk '{print $9}')
    [[ -z $img_file ]] && echo 'Something went wrong img file not found after unzip... exiting' && exit 1
}

main() {
    clear
    if ! $configure_wpa_supplicant && [[ ! -f "$(pwd)/wpa_supplicant.conf" ]]; then
        echo "wlan configuration will not be applied to image, to apply WLAN configuration break out of the script & change params @"
        echo "top of this script *or* provide wpa_supplicant.conf in script directory."
    fi
        
    my_usb=$(ls -l /dev/disk/by-path/*usb* 2>/dev/null |grep -v part | sed 's/.*\(...\)/\1/')
    [[ $my_usb ]] && boot_list=($(sudo fdisk -l |grep -o '/dev/sd[a-z][0-9]  \*'| cut -d'/' -f3| awk '{print $1}'))
    [[ $boot_list =~ $my_usb ]] && my_usb=    # if usb device found make sure it's not marked as bootable if so reset my_usb so we can check for sd card adapter
    [[ -z $my_usb ]] && my_usb=$( sudo fdisk -l | grep 'Disk /dev/mmcblk' | awk '{print $2}' | cut -d: -f1 | cut -d'/' -f3)
    ####[[ -z $my_usb ]] && echo "Script currently only support USB micro-sd adapters... none found... Exiting" && exit 1
    
    echo -e "\n\n\033[1;32mConsolePi Image Creator$*\033[m \n'exit' (which will terminate the script) is valid at all prompts\n"
    [[ $my_usb ]] && echo -e "Script has discovered removable flash device @ \033[1;32m ${my_usb} $*\033[m" ||
        echo -e "Script failed to detect removable flash device, you will need to specify the device"
    prompt="Do you want to see fdisk details for all disks to verify?"
    get_input

    # Display fdisk -l output if user wants to verify the correct drive is selected
    if $input; then
        echo "Displaying fdisk -l output in 'less' press q to quit"
        sleep 3
        sudo fdisk -l | less
    fi
    
    # Give user chance to change target drive
    echo -e "\n\nPress enter to accept \033[1;32m ${my_usb} $*\033[m as the destination drive or specify the correct device (i.e. 'sdc' or 'mmcblk0')"
    read -p "Device to flash with image [${my_usb}]:" drive
    [[ ${drive,,} == "exit" ]] && echo "Exit based on user input." && exit 1
    
    if [[ $drive ]]; then
        [[ $boot_list =~ $drive ]] && prompt="The selected drive contains a bootable partition, are you sure about this?" && get_input
        ! $input && echo "Exiting based on user input" && exit 1
        drive_list=( $(sudo fdisk -l | grep 'Disk /dev/' | awk '{print $2}' | cut -d'/' -f3 | cut -d':' -f1) )
        [[ $drive_list =~ $drive ]] && echo "${my_usb} not found on system. Exiting..." && exit 1
        my_usb=$drive
    fi
    
    [[ -z $my_usb ]] && echo "Something went wrong no destination device selected... exiting" && exit 1

    # umount device if currently mounted
    go_umount=true
    while $go_umount; do
        mount_point=$(mount | tail -1 | grep "${my_usb}" | awk '{print $3}')
        [[ ! -z $mount_point ]] && sudo umount $mount_point && echo "un-mounting $mount_point" || go_umount=false
    done

    # get raspbian-lite image if not in script dir
    echo "Getting raspbian-lite image"
    
    # Find out what current raspbian release is
    cur_rel=$(curl -sIL https://downloads.raspberrypi.org/raspbian_lite_latest | 
        grep -o -E "[0-9]{4}-[0-9]{2}-[0-9]{2}-raspbian-[a-z,A-Z]*-lite.zip" | head -1 | cut -d'.' -f1)
    
    # Check to see if any images exist in script dir already
    found_img_file=$(ls -lc *raspbian*-lite.img 2>>/dev/null | awk '{print $9}')
    found_img_zip=$(ls -lc *raspbian*-lite.zip 2>>/dev/null | awk '{print $9}')
    # img_file=$(ls -lc "${found_img_file}.img" 2>>/dev/null | awk '{print $9}')
    
    # If img or zip raspbian-lite image exists in script dir see if it is current
    # if not prompt user to determine if they want to download current
    if [[ $found_img_file ]]; then
        if [[ ! ${found_img_file%.img} == $cur_rel ]]; then
            echo "${found_img_file%.img} found, but the latest available release is ${cur_rel}"
            prompt="Would you like to download and use the latest release? (${cur_rel}):"
            get_input
            $input || img_file=$found_img_file
        else
            echo "Using image ${found_img_file%.img}, found in $(pwd). It is the current release"
            img_file=$found_img_file
        fi
    elif [[ $found_img_zip ]]; then
        if [[ ! ${found_img_zip%.zip} == $cur_rel ]]; then
            echo "${found_img_zip%.zip} found, but the latest available release is ${cur_rel}"
            prompt="Would you like to download and use the latest release? (${cur_rel}):"
            get_input
            $input || do_unzip $found_img_zip #img_file assigned in do_unzip
        else
            echo "Using ${found_img_zip} found in $(pwd). It is the current release"
            do_unzip $found_img_zip
            #img_file assigned in do_unzip
        fi
    else
        echo "no image found in $(pwd)"
    fi
    
    # img_file will only be assigned if an image was found in the script dir
    retry=1
    while [[ -z $img_file ]] ; do
        [[ $retry > 3 ]] && echo "Exceeded retries exiting " && exit 1
        echo "downloading image from raspberrypi.org.  Attempt: ${retry}"
        curl -JLO https://downloads.raspberrypi.org/raspbian_lite_latest
        do_unzip "${cur_rel}.zip"
        ((retry++))
    done
   
    # Burn Raspian image to device (micro-sd)
    echo -e "\n\n!!! Last chance to abort !!!"
    prompt="About to burn '${img_file}' to ${my_usb}, Continue?" 
    get_input
    ! $input && echo 'Exiting Script based on user input' && exit 1
    echo -e "\nNow Burning image ${img_file} to ${my_usb} standby...\n this takes a few minutes\n"
    sudo dd bs=4M if="${img_file}" of=/dev/${my_usb} conv=fsync status=progress && echo -e "\n\n\033[1;32mImage written to flash - no Errors$*\033[m\n\n" || 
        ( echo "\n\n\033[1;32mError occurred burning image $*\033[m\n\n" && exit 1 )

    echo "Mounting boot partition to enable ssh"
    # Create some mount-points if they don't exist already.  Script will remove them if it has to create them, they will remain if they were already there
    [[ ! -d /mnt/usb1 ]] && sudo mkdir /mnt/usb1 && usb1_existed=false || usb1_existed=true
    [[ ! -d /mnt/usb2 ]] && sudo mkdir /mnt/usb2 && usb2_existed=false || usb2_existed=true

    # Mount boot partition
    ( [[ ${my_usb} =~ "mmcblk" ]] && sudo mount /dev/${my_usb}p1 /mnt/usb1 ) || sudo mount /dev/${my_usb}1 /mnt/usb1
    [[ $? > 0 ]] && echo 'Error mounting boot partition' && exit 1
    
    # Create empty file ssh in boot partition
    echo "Enabling ssh on image"
    sudo touch /mnt/usb1/ssh && echo -e "SSh is now enabled\n" || echo 'Error enabling SSH... script will continue anyway'
    
    # move any overlay files to /boot/overlays (usb1/overlays)
    [[ -f $(ls *.dtbo) ]] && cp *.dtbo /mnt/usb1/overlays && echo "found overlay files in script dir moved to /boot/overlays dir"
    
    # Done with boot partition unmount
    sudo umount /mnt/usb1

    echo -e "\n\nMounting System partition to Configure ConsolePi auto-install and copy over any pre-config files found in script dir"
    [[ ${my_usb} =~ "mmcblk" ]] && sudo mount /dev/${my_usb}p1 /mnt/usb2 ||
      sudo mount /dev/${my_usb}2 /mnt/usb2
    [[ $? > 0 ]] && echo 'Error mounting system partition' && exit 1
    
    #Configure simple psk SSID based on params in this script
    if $configure_wpa_supplicant; then
        echo -e "Configuring wpa_supplicant.conf | defining ${ssid}"
        sudo echo "country=${wlan_country}" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        sudo echo "network={" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        sudo echo "        ssid=\"${ssid}\"" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        sudo echo "        psk=\"${psk}\"" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        [[ $priority > 0 ]] && sudo echo "        priority=${priority}" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
        sudo echo "}" >> "/mnt/usb2/etc/wpa_supplicant/wpa_supplicant.conf"
    else
        echo 'Script Option to pre-config psk ssid not enabled'
    fi
   
    # Configure pi user to auto-launch ConsolePi installer on first-login
    if $auto_install; then
        echo 'auto-install enabled, configuring pi user to auto-launch ConsolePi installer on first-login'
        sudo echo "consolepi-install" >> /mnt/usb2/home/pi/.bashrc
    fi

    # create auto install command/script
    [[ ! -d /mnt/usb2/usr/local/bin ]] && sudo mkdir /mnt/usb2/usr/local/bin
    sudo echo '#!/usr/bin/env bash' > /mnt/usb2/usr/local/bin/consolepi-install
    sudo echo "sudo wget -q https://raw.githubusercontent.com/Pack3tL0ss/ConsolePi/master/installer/install.sh -O /tmp/ConsolePi && sudo bash /tmp/ConsolePi && sudo rm -f /tmp/ConsolePi" \
          >> /mnt/usb2/usr/local/bin/consolepi-install

    # make install command/script executable
    sudo chmod +x /mnt/usb2/usr/local/bin/consolepi-install || echo 'ERROR making consolepi-install command/script executable'

    # Look for pre-configuration files in script dir.  Also if ConsolePi_stage subdir is found in script dir cp the dir to the ConsolePi image
    cur_dir=$(pwd)
    pi_home="/mnt/usb2/home/pi"
    [[ -f "${cur_dir}/ConsolePi.conf" ]] && cp "${cur_dir}/ConsolePi.conf" $pi_home  && echo "ConsolePi.conf found pre-staging on image"
    [[ -f "${cur_dir}/ConsolePi.ovpn" ]] && cp "${cur_dir}/ConsolePi.ovpn" $pi_home && echo "ConsolePi.ovpn found pre-staging on image"
    [[ -f "${cur_dir}/ovpn_credentials" ]] && cp "${cur_dir}/ovpn_credentials" $pi_home && echo "ovpn_credentials found pre-staging on image"
    [[ -d "${cur_dir}/ConsolePi_stage" ]] && sudo mkdir $pi_home/staged && sudo cp "${cur_dir}"/ConsolePi_stage/* $pi_home/staged && echo "ConsolePi_stage dir found Pre-Staging all files"
    
    # if wpa_supplicant.conf exist in script dir cp it to ConsolePi image.
    # if EAP-TLS SSID is configured in wpa_supplicant extract EAP-TLS cert details and cp certs (not a loop only good to pre-configure 1)
    #   certs should be in script dir or 'cert' subdir cert_names are extracted from the wpa_supplicant.conf file found in script dir
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
            [[ -d cert ]] && cd cert    # if script dir contains cert subdir look there for certs - otherwise look in script dir
            [[ ! -d $cert_path ]] && sudo mkdir "${cert_path}" # Will only work if all but the final folder already exists - I don't need more so...
            [[ -f ${client_cert##*/} ]] && sudo cp ${client_cert##*/} "${cert_path}/${client_cert##*/}"
            [[ -f ${ca_cert##*/} ]] && sudo cp ${ca_cert##*/} "${cert_path}/${ca_cert##*/}"
            [[ -f ${private_key##*/} ]] && sudo cp ${private_key##*/} "${cert_path}/${private_key##*/}"
            cd "${cur_dir}"
        fi
    fi    

    # Done prepping system partition un-mount
    sudo umount /mnt/usb2
    
    # Remove our mount_points if they didn't happen to already exist when the script started
    ! $usb1_existed && rmdir /mnt/usb1
    ! $usb2_existed && rmdir /mnt/usb2

    echo -e "\npi zero flash drive ready\n\n"
    echo "Boot RaspberryPi with this image, if auto-install was disabled in script enter 'consolepi-install' to deploy ConsolePi"
}


iam=`whoami`
if [ "${iam}" = "root" ]; then 
    main
else
    echo 'Script should be ran as root. exiting.'
fi
