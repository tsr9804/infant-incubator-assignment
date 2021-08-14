import socket
import ssl

s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

HOST_ADDR = '127.0.0.1'
HOST_PORT = 23456
SERVER_SNI_HOSTNAME = 'example.com'
SERVER_CERT = 'certs/server.crt'
CLIENT_CERT = 'certs/client.crt'
CLIENT_KEY = 'certs/client.key'


def simulate_client_temp_display(temp):
    return temp - 273


def authenticate(p, pw):
    s.sendto(b"AUTH %s" % pw, ("127.0.0.1", p))
    msg, addr = s.recvfrom(1024)
    return msg.strip()


# vulnerability #1 test
def test_auth_bypass(p):
    try:
        s.sendto(b"AUTH ;GET_TEMP", ("127.0.0.1", p))
        msg, addr = s.recvfrom(1024)
        m = msg.decode("utf-8").strip()

        # If the message received is not none and is anything other than
        # 'Authenticate First' or 'Bad Command' then the command was
        # successfully executed without the proper permissions
        assert(m and (m != "Authenticate First" and m != "Bad Command"))
    except Exception as ex:
        print(ex)
        assert(1 == 2)


# vulnerability  #2 test
def test_bad_temp_response(p):
    try:
        incToken = authenticate(p, b"!Q#E%T&U8i6y4r2w")
        s.sendto(b"%s;SET_DEGC" % incToken, ("127.0.0.1", p))
        s.sendto(b"%s;GET_TEMP" % incToken, ("127.0.0.1", p))
        msg, addr = s.recvfrom(1024)
        m = float(msg.decode("utf-8"))
        display_temp = simulate_client_temp_display(m)

        # The display_temp represents what will be displayed to the client on
        # the graph that shows the temperatures. In this case if the temperature
        # is set to C then the display temp goes below -200 which is not the
        # actual temperature
        assert(display_temp < -200)
    except Exception as ex:
        print(ex)
        assert(1 == 2)


# vulnerability #3 test
def test_same_pass(p1, p2):
    try:
        incToken1 = authenticate(p1, b"!Q#E%T&U8i6y4r2w")
        incToken2 = authenticate(p2, b"!Q#E%T&U8i6y4r2w")

        # The thermometer for both the incubator and human are using the same
        # hard-coded credentials which is a vulnerability
        assert(incToken1 and incToken2)
    except Exception as ex:
        print(ex)
        assert (1 == 2)


# vulnerability #4 test
def test_for_unencrypted(p):
    try:
        incToken = authenticate(p, b"!Q#E%T&U8i6y4r2w")
        s.sendto(b"%s;GET_TEMP" % incToken, ("127.0.0.1", p))
        msg, addr = s.recvfrom(1024)
        m = float(msg.decode("utf-8"))

        # If this assertion passed that means the communication was not
        # encrypted. If it was encrypted, the response would need to have been
        # decrypted in order to be properly converted.
        assert (isinstance(m, float))
    except Exception as ex:
        print(ex)
        assert (1 == 2)


def test_for_valid_tls():
    try:
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH,
                                             cafile=SERVER_CERT)
        context.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn = context.wrap_socket(sock, server_side=False,
                                   server_hostname=SERVER_SNI_HOSTNAME)
        conn.connect((HOST_ADDR, HOST_PORT))
        conn.send(b"GET_TEMP")
        data = float(conn.recv(4096).decode('utf-8'))

        # if a proper float is received then the TLS connection was successful
        # and the client cert was validated on the server's end.
        assert(isinstance(data, float))
    except Exception as ex:
        print(ex)
        assert (1 == 2)
    finally:
        conn.send(b"LOGOUT")
        conn.close()


test_for_valid_tls()
