set -e
exec 3<>/dev/tcp/$1/$2
cat <&3 &
exec >-
cat >&3
wait
