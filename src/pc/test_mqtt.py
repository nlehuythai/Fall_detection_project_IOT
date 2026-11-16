import socket

broker = "test.mosquitto.org"
port = 1883

try:
    sock = socket.create_connection(
        (broker, port),
        timeout=10
    )

    print("✓ TCP connection successful!")
    print("Broker:", broker)
    print("Port:", port)

    sock.close()

except Exception as e:
    print("✗ Connection failed:", e)