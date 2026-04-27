const socket = io("http://127.0.0.1:5000");

socket.on("connect", () => {
    console.log("Connected to server!");
});

socket.on("disconnect", () => {
    console.log("Disconnected from server!");
});