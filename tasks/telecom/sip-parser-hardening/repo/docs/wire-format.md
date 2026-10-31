# Accepted wire format

```
message      = start-line CRLF *(header CRLF) CRLF [ body ]
start-line   = request-line / status-line
request-line = Method SP Request-URI SP "SIP/2.0"
status-line  = "SIP/2.0" SP 3DIGIT SP Reason-Phrase
header       = name ":" value   ; leading/trailing whitespace of value ignored
```

* Header names are case-insensitive; compact forms map to long names
  (`v` Via, `f` From, `t` To, `i` Call-ID, `l` Content-Length, `m` Contact,
  `c` Content-Type).
* The body is opaque bytes. With `Content-Length`, exactly that many bytes are the
  body and anything after it is discarded (datagram semantics, RFC 3261 §18.3).
  Without it, the rest of the datagram is the body.
