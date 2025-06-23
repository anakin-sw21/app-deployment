from app import create_app

app, socket_io = create_app()

if __name__ == "__main__":
    socket_io.run(app, host='0.0.0.0', debug=True)
