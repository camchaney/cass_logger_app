"""
Example: Download and plot suspension travel data from a Cass Logger recording.

This script shows a simple example of how to load binary files

Workflow
--------
1. ``import_data`` — loads a pre-downloaded ``.bin`` file from the
   ``examples/data/`` directory and parses it into a DataFrame using
   ``CassCommands.process_data_file``.
2. ``plot_data`` — applies the ADC-to-millimetre gain constants and
   displays a two-panel time-series plot.

Data columns used
-----------------
- ``t``  : elapsed time in seconds (derived from the ``tmicros`` field)
- ``a0`` : fork potentiometer raw ADC reading (scaled by ``FORK_GAIN``)
- ``b0`` : shock potentiometer raw ADC reading (scaled by ``SHOCK_GAIN``)

Constants
---------
FORK_GAIN : float
    Converts raw ``a0`` ADC counts to millimetres of fork travel.
SHOCK_GAIN : float
    Converts raw ``b0`` ADC counts to millimetres of shock travel.

Notes
-----
- The example ``.bin`` file must already exist in ``examples/data/``.
  To download live data from a connected device use
  ``CassCommands.download_all()`` instead.
- ``process_data_file`` defaults to the ``"std"`` firmware dtype; pass
  the ``fw_ver`` keyword if the file was recorded with an I2C firmware
  variant.

Usage
-----
Run directly::

    python examples/download_and_process_example.py
"""

import src.cass_commands as cass_commands
from pathlib import Path
from matplotlib import pyplot as plt
import pandas as pd

FORK_GAIN = 4.884e-02
SHOCK_GAIN = 2.442e-02

cass_util = cass_commands.CassCommands()


def download_data():
    """Download example data from a connected Cass Logger.

    Returns
    -------
    Path
        Path to the directory where the data was downloaded.
    """
    return cass_util.download_all()


def plot_internal_imu_data(data_dir: str):
    """Plot fork and shock suspension travel against time.

    NOTE: This is for the existing data in the examples/data dir.

    Applies the ADC-to-millimetre gain constants to the raw potentiometer
    channels and renders a two-panel time-series figure using matplotlib.

    Parameters
    ----------
    example_data : pd.DataFrame
        DataFrame returned by ``import_data``. Must contain columns
        ``t``, ``a0``, and ``b0``.
    """
    for file in Path(data_dir).glob("*.bin"):
        example_data = cass_util.process_data_file(file)
        plt.style.use("ggplot")

        fig, axs = plt.subplots(nrows=3, ncols=1, sharex=True, figsize=(12, 8))
        for ax in axs:
            ax.tick_params(axis="x", labelbottom=True)
        axs[0].plot(example_data["t"], example_data["gx"])
        axs[1].plot(example_data["t"], example_data["gy"])
        axs[2].plot(example_data["t"], example_data["gz"])

        # labeling / formatting
        axs[0].set_title(f"Internal IMU - X Acceleration {file.name}")
        axs[1].set_title(f"Internal IMU - Y Acceleration {file.name}")
        axs[2].set_title(f"Internal IMU - Z Acceleration {file.name}")
        plt.title("Example data plot")
        axs[0].set_xlabel("time [s]")
        axs[0].set_ylabel("accel [m/s^2]")
        axs[1].set_xlabel("time [s]")
        axs[1].set_ylabel("accel [m/s^2]")
        axs[2].set_xlabel("time [s]")
        axs[2].set_ylabel("accel [m/s^2]")

        plt.tight_layout()
        plt.show()


def test_delete():
    print(cass_util.list_files())
    bSucess = cass_util.delete_all_files(prompt_user=True)
    if bSucess:
        print("Success!!!")
    print(cass_util.list_files())


if __name__ == "__main__":
    data_dir = download_data()
    print(data_dir)
    plot_internal_imu_data(data_dir)
    test_delete()
