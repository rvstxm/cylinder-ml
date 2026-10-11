#!/bin/bash
N=5
cd ~/cylinder-ml/cases/sweep_v1 || exit 1

run_one() {
    cd "$1" || return
    if ./Allrun > allrun.out 2>&1 && grep -q "^End" log.foamRun; then
        echo "$(date +%H:%M) готово  $1"
    else
        echo "$(date +%H:%M) ОШИБКА  $1"
    fi
}
export -f run_one

{ ls -d Re4* Re5* 2>/dev/null; ls -d Re*; } | awk '!seen[$0]++' | xargs -P "$N" -I{} bash -c 'run_one {}'

echo "$(date +%H:%M) ВСЁ ЗАКОНЧЕНО"
