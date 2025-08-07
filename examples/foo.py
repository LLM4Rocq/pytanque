from pytanque import Pytanque
import logging
import subprocess
import time

logging.basicConfig()
logging.getLogger("pytanque.client").setLevel(logging.INFO)

# First launch the server
pet_port = 8777
pet_server = subprocess.Popen(
    ["pet-server", "-p", str(pet_port)],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

time.sleep(5)  # Wait for pet-server to start

# You can now interact with the server using Pytanque
with Pytanque("127.0.0.1", pet_port) as pet:
    pet.set_workspace(debug=False, dir="./examples/")
    print(pet.toc(file="./examples/foo.v"))
    s0 = pet.start(file="./examples/foo.v", thm="addnC")
    s = pet.run(s0, "timeout 1 induction n.", verbose=True)
    g = pet.goals(s)
    # print(pet.premises(s))
    s = pet.run(s, "simpl.", verbose=True)
    g = pet.goals(s)
    s = pet.run(s0, "by elim: n => //= ? ->.", verbose=True)
    print("State:", s)

# Do not forget to close the server
try:
    pet_server.terminate()
    pet_server.wait(timeout=10)  # Give server time to cleanup
except subprocess.TimeoutExpired:
    pet_server.kill()
    pet_server.wait()
