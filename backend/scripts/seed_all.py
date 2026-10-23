from app import create_app

from . import seed_admin, seed_demo

SEEDS = [
    seed_admin,  # администратор из .env — всегда первым
    seed_demo,
    # сюда добавлять новые скрипты
]

if __name__ == "__main__":
    app = create_app(log_name="seed")
    with app.app_context():
        for seed in SEEDS:
            seed.run()
