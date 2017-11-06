backend {{ app_name }} {
    .host = "127.0.0.1";
    .port = "{{ app_port }}";
}

sub vcl_recv {
    if (req.http.host ~ "^{{ app_domain }}$") { set req.backend = {{ app_name }}; }
}

sub vcl_fetch {
    set beresp.ttl = 3600s;
    return(deliver);
}
