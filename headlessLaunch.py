import subprocess, schedule
import time

def run_test(testPath, comPort):
    subprocess.run(["west", "twister", "-T", testPath,
                    "--device-testing", "--device-serial",
                    comPort,"-p", "lp_em_cc2340r53",
                    "-W","--short-build-path",
                    "--west-flash", "--flash-timeout=120"])

def test_runner():
    run_test(test,com)

test = input("Relative testpath for the test: ")
com = input("COM Port for the board: ")
testTime = input("Time to run in format [15:30]: ")

schedule.every().day.at(testTime).do(test_runner)
print(f"TEST SCHEDULED AT TIME: {testTime}")

while True:
    schedule.run_pending()
    time.sleep(1)