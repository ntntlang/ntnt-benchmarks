wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"
wrk.body = '{"message":"Hello, World!","numbers":[1,2,3,4,5],"nested":{"key":"value"}}'
