# Gunicorn configuration file for Admin Panel
import multiprocessing

bind = "0.0.0.0:5002"
workers = 2  # Admin panel doesn't need many workers
threads = 2
timeout = 120
keepalive = 2
accesslog = "-"
errorlog = "-"
loglevel = "info"
worker_class = "gthread"
