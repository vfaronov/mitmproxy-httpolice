#!/usr/bin/expect --

# Run this inside the virtual environment (if you're using one).
# Requires nc, curl, and nghttp on $PATH, and a reasonably recent OpenSSL.
# Caution: Under some circumstances, this script might mess up your terminal,
# so best to run this in a separate one.

# In Travis builds, urwid under expect thinks it's running in a 0x0 terminal
# unless I initialize this explicitly.
stty columns 80 rows 25

# Don't pass the spawned commands' output to the controlling terminal.
log_user 0

set timeout 3
set port 31994
set scriptpath [exec python -m mitmproxy_httpolice]
set workdir [exec mktemp --directory --tmpdir "XXX.mitmproxy-httpolice-test"]
set reportpath "$workdir/report"
set nghttp_features [exec nghttp --help]

proc die {msg} {
    puts $msg
    exit 1
}

puts "spawning mitmproxy"
spawn mitmproxy --confdir "$workdir/conf" --listen-port $port \
    --scripts $scriptpath \
    --set httpolice_silence=1277 --set httpolice_mark=error
expect ":$port"

puts "running as HTTP/1.1 forward proxy"
exec curl -sx "http://localhost:$port" "httpbin.org/stream/10"
exec curl -sx "http://localhost:$port" "httpbin.org/response-headers?Etag=123"
exec curl -sx "http://localhost:$port" "test.invalid/"

puts "check flow marking"
expect {
    "●" {}
    timeout {die "no mark on flows with errors!"}
}

puts "running as HTTP/1.1 reverse proxy"
send ":set mode=reverse:http://httpd.apache.org\r"
sleep 1
exec nc -Cq0 localhost $port << "OPTIONS * HTTP/1.1\nHost: localhost:$port\n\n"

puts "checking that /+httpolice/ responds with error message"
exec curl -s "http://localhost:$port/+httpolice/" -o "$reportpath.html"
exec grep -F "No report has been" "$reportpath.html"
exec rm -f "$reportpath.html"

puts "generating HTML report in memory"
send ":httpolice.report.html @all -\r"
expect {
    "in memory" {}
    timeout {die "no acknowledgement alert from command!"}
}

puts "checking that /+httpolice/ serves the report"
exec curl -s "http://localhost:$port/+httpolice/" -o "$reportpath.html"
exec grep -F "Bad JSON body" "$reportpath.html"
exec rm -f "$reportpath.html"

puts "running as HTTP/2 reverse proxy"
send ":set mode=reverse:https://h2o.examp1e.net\r"
sleep 1
set nghttp [list nghttp --verbose --null-out]
if {[string first "--no-verify-peer" $nghttp_features] > 0} {
    lappend nghttp --no-verify-peer
}
exec {*}$nghttp "https://localhost:$port/"

puts "generating reports"
send ":httpolice.report.html @all $reportpath.html\r"
send ":httpolice.report.text @all $reportpath.txt\r"
expect {
    "HTTPolice: wrote report on" {}
    timeout {die "no acknowledgement alert from command!"}
}

puts "checking flow details UI"
# enter the first flow and go to its Details pane
send ":console.nav.select\r"
send ":console.nav.next\r"
send ":console.nav.next\r"
expect {
    "E 1038 Bad JSON body" {}
    timeout {die "no notice 1038 title!"}
}

puts "checking silencing"
send ":view.focus.next\r"
expect {
    "C 1277" {die "got silenced notice 1277!"}
}

puts "checking event log"
send ":console.view.eventlog\r"
expect {
    "warn: HTTPolice: " {}
    timeout {die "no warning in event log!"}
}

puts "exiting mitmproxy"
send ":console.exit\r"
wait

puts "checking reports"
exec grep -F "!DOCTYPE html" "$reportpath.html"
exec grep -F "Bad JSON body" "$reportpath.html"
exec grep -F "E 1038 Bad JSON body" "$reportpath.txt"
exec grep -F "as part of entity-tag" "$reportpath.html"
exec grep -F "E 1000 Syntax error in ETag header" "$reportpath.txt"
exec grep -F "test.invalid" "$reportpath.html"
exec grep -F "OPTIONS" "$reportpath.html"
exec grep -F "OPTIONS *" "$reportpath.txt"
exec grep -F "https://h2o.examp1e.net/" "$reportpath.html"
exec grep -F "HTTP/2" "$reportpath.html"
# promised requests
exec grep -F "https://h2o.examp1e.net/assets/" "$reportpath.html"
exec grep -F "GET https://h2o.examp1e.net/assets/" "$reportpath.txt"

puts "all tests OK"

exec rm -rf $workdir
