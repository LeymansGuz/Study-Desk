package system.authz
import rego.v1
default allow := false

allow if {
    input.identity == data.local_security.token
    input.method == "GET"
    input.path == ["health"]
}

allow if {
    input.identity == data.local_security.token
    input.method == "POST"
    input.path == ["v1", "data", "tutor", "decision"]
}
