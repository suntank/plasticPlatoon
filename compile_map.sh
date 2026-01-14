#!/bin/bash

# q2map compiler script
# Usage: ./compile_map.sh --map <mapname> [--vis] [--rad]

# Default values
BASEDIR="/home/austin-morgan/Documents/plasticPlatoon/release/baseq2"
MAPS_DIR="$BASEDIR/maps"
Q2TOOL="~/Documents/q2tools/Linux64/q2tool"

# Parse arguments
VIS=false
RAD=false
MAP_NAME=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --map)
            MAP_NAME="$2"
            shift 2
            ;;
        --vis)
            VIS=true
            shift
            ;;
        --rad)
            RAD=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 --map <mapname> [--vis] [--rad]"
            echo "  --map <mapname>  Required: Name of the map file (without .map extension)"
            echo "  --vis            Optional: Run VIS compilation"
            echo "  --rad            Optional: Run RAD compilation"
            echo "  -h, --help       Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$MAP_NAME" ]]; then
    echo "Error: --map argument is required"
    echo "Use -h or --help for usage information"
    exit 1
fi

# Construct map file path
MAP_FILE="$MAPS_DIR/${MAP_NAME}.map"

# Check if map file exists
if [[ ! -f "$MAP_FILE" ]]; then
    echo "Error: Map file not found: $MAP_FILE"
    exit 1
fi

# Build the command
COMMAND="$Q2TOOL -bsp"

if [[ "$VIS" == true ]]; then
    COMMAND="$COMMAND -vis"
fi

if [[ "$RAD" == true ]]; then
    COMMAND="$COMMAND -rad"
fi

COMMAND="$COMMAND -basedir $BASEDIR $MAP_FILE"

# Execute the command
echo "Running: $COMMAND"
exec $COMMAND
