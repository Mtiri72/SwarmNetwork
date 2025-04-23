#!/bin/bash


# Set the working directory to where the script path is stored
# This makes the script executable from anywhere
SCRIPT_PATH="${BASH_SOURCE[0]:-$0}";
cd "$( dirname -- "$SCRIPT_PATH"; )";

# Check if number of parameters passed to the script is equal to 2
if [ "$#" != '2' ] || [[ "${BASH_SOURCE[0]}" == "${0}" ]] ; then
    echo -e "\e[32mError:\e[0m"
    echo -e "Script must be sourced with parameters: \nparam1 Script Type: [ap, co, sn] \nparam2 Log LeveL: [10,20,30,40,50] where 10 is for Debug, 20 for info, 30 for warning, 40 for Error, and 50 is for Critical"
    echo -e "for example:\nsource ./run.sh ap 1\n"
    exit
fi


# read the script Role from first parameters and the numeric ID of the node from the second parameter
export ROLE=$1
# export NUMID=$2
export LOG_LEVEL=$2

source ./shell_scripts/run2.sh $ROLE $LOG_LEVEL