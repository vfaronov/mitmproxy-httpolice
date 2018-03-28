#!/usr/bin/expect --

# Usage: tools/integration_tests.tcl [-http2]
#
# Run this inside the virtualenv (if you're using one).
# -http2 requires nghttp on $PATH, as well as a reasonably recent OpenSSL.
#
# Run this in a separate terminal, or reset your terminal after running,
# because the stty invocation below doesn't seem to be undone by expect
# even on a successful exit.

# In Travis builds, urwid under expect thinks it's running in a 0x0 terminal
# unless I initialize this explicitly.
stty columns 80 rows 25

# Don't pass the spawned commands' output to the controlling terminal.
log_user 0

set with_http2 {[lsearch -exact $argv -http2] >= 0}
set timeout 3
set port 31994
set scriptpath [exec python -m mitmproxy_httpolice]
set reportpath "/tmp/httpolice-report"

puts "spawning mitmproxy"
spawn mitmproxy --conf /dev/null --listen-port $port \
    --scripts $scriptpath --set httpolice_silence=1277
expect ":$port"

puts "running as HTTP/1.1 forward proxy"
exec curl -sx "http://localhost:$port" "httpbin.org/stream/10"
exec curl -sx "http://localhost:$port" "httpbin.org/response-headers?Etag=123"

puts "running as HTTP/1.1 reverse proxy"
send ":set mode=reverse:http://httpd.apache.org\r"
sleep 1
exec nc -C localhost $port << "OPTIONS * HTTP/1.1\nHost: localhost:$port\n\n"

if $with_http2 {
    puts "running as HTTP/2 reverse proxy"
    send ":set mode=reverse:https://h2o.examp1e.net\r"
    sleep 1
    exec nghttp -vn "https://localhost:$port/"
}

puts "generating reports"
send ":httpolice.report.html @all $reportpath.html\r"
send ":httpolice.report.text @all $reportpath.txt\r"
expect {
    "HTTPolice: wrote report on" {}
    timeout {
        puts "no acknowledgement alert from command!"
        exit 1
    }
}

puts "checking flow details UI"
# enter the first flow and go to its Details pane
send ":console.nav.select\r"
send ":console.nav.next\r"
send ":console.nav.next\r"
expect {
    "E 1038 Bad JSON body" {}
    timeout {
        puts "no notice 1038 title!"
        exit 1
    }
}

puts "checking silencing"
send ":view.focus.next\r"
expect {
    "C 1277" {
        puts "got silenced notice 1277!"
        exit 1
    }
}

puts "checking event log"
send ":console.view.eventlog\r"
expect {
    "warn: HTTPolice: " {}
    timeout {
        puts "no warning in event log!"
        exit 1
    }
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
exec grep -F "OPTIONS" "$reportpath.html"
exec grep -F "OPTIONS *" "$reportpath.txt"
if $with_http2 {
    exec grep -F "https://h2o.examp1e.net/" "$reportpath.html"
    exec grep -F "HTTP/2" "$reportpath.html"
    # promised requests
    exec grep -F "https://h2o.examp1e.net/assets/" "$reportpath.html"
    exec grep -F "GET https://h2o.examp1e.net/assets/" "$reportpath.txt"
}

puts "all tests OK"
