from collections.abc import Sequence

def flatten_index(row: int, col: int, cols: int) -> int:
    if cols <= 0:
        raise ValueError("cols must be positive.")
    if row < 0 or col < 0:
        raise ValueError("row and col must be non-negative.")
    return (row * cols) + col


def extract_active_indices(mask: Sequence[int]) -> list[int]:
    active_indices: list[int] = []
    for index, cell_mask in enumerate(mask):
        if cell_mask not in (0, 1):
            raise ValueError("mask entries must be 0 or 1.")
        if cell_mask == 1:
            active_indices.append(index)
    return active_indices


def extract_sparse_values(
    values: Sequence[float | None],
    active_indices: Sequence[int],
) -> list[float]:
    sparse_values: list[float] = []
    for index in active_indices:
        if index < 0 or index >= len(values):
            raise ValueError("active index is out of range for values array.")

        value = values[index]
        if value is None:
            raise ValueError("active index points to a null value.")

        sparse_values.append(float(value))

    return sparse_values
