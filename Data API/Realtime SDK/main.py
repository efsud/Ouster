from realtime_subscriber.Realtime_subscriber_api import BCTWSConnection

def main():
    username = "" # Enter your username here
    password = "" # Enter your password here
    UDID = "" # Enter your UDID here

    stream = BCTWSConnection(UDID=UDID, username=username, password=password,singleton=True, 
                             subscriptions=[BCTWSConnection.subscriptionOption.FRAME,BCTWSConnection.subscriptionOption.PHASE_CHANGE,BCTWSConnection.subscriptionOption.LOOP_CHANGE], 
                             semantic_abs=False)
    while True:
        data = stream.get_hyperparameter()
        print(data)

   


if __name__ == "__main__":
    main()
