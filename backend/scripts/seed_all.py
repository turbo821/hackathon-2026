from app import create_app
from . import seed_messages

SEEDS = [
    seed_messages,
    # сюда добавлять новые скрипты
]

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        for seed in SEEDS:
            seed.run()