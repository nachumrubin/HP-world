#!/bin/bash
# Screenshot from any camera spot, no C++ rebuild:  Tools/shot_at.sh name x y z lookx looky lookz   (metres; X north, Y east)
# Moves the level's PlayerStart (rewrites M0_Greybox.umap; rebuild with build_greybox_m0.py to reset), runs the game and takes a HighResShot.
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1
P="$(pwd -W)/HPWorld.uproject"
HPW_POS="$2,$3,$4" HPW_LOOK="$5,$6,$7" "/d/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" "$P" -run=pythonscript -script="$(pwd -W)/Tools/Unreal/move_player_start.py" -unattended -nosplash -stdout > /dev/null 2>&1
mkdir -p Tools/generated/shots
HPW_SHOT_NAME="$1" timeout 300 "/d/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe" "$P" /Game/HPW/Maps/M0_Greybox -game -windowed -ResX=1600 -ResY=900 -nosound -log -unattended -ExecCmds="py $(pwd -W)/Tools/Unreal/shots_py.py" > Saved/shots_run.log 2>&1
ls -la "Tools/generated/shots/$1.png"
