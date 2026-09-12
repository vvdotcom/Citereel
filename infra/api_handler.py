from mangum import Mangum

from launchpad_api.main import app

handler = Mangum(app, lifespan="off")
