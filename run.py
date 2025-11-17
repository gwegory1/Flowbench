"""Simple launcher for FlowBench."""
from flowbench.main import main


if __name__ == '__main__':
    raise SystemExit(main(__import__('sys').argv))
