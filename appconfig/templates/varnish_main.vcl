sub vcl_recv {
    set req.http.Host = regsub(req.http.Host, "^www\.", "");
    set req.http.Host = regsub(req.http.Host, ":80$", "");
}

include "/etc/varnish/sites.vcl";
