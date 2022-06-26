var fs = require("fs");
var stdinBuffer = fs.readFileSync(0); // STDIN_FILENO = 0
var s = stdinBuffer.toString()
var ss = s.split(" ")
var a = parseInt(ss[0])
var b = parseInt(ss[1])
console.log(a + b);