# Docking-station MSP430F5529

Choose one CCS project for the station. The car uses a separate [supervisor](../../Car/MSP430/robot_supervisor).

| Project folder | How a refill starts | Laptop connection |
| --- | --- | --- |
| [standalone](standalone) | A clear bay followed by a confirmed magnet starts a three-second wait. A sufficient reservoir allows a timed refill. | USB is optional for status. The station runs the sequence locally. |
| [waterlevel](waterlevel) | The station confirms the magnet and waits for a matching stop permit from the laptop before settling and pumping. | The dashboard must renew the permit. A matching full-tank message ends the refill early. |

Each project includes `main.c`, the supplied `lcd16.c` and `lcd16.h`, the device linker file and the CCS project and debugger settings. The standalone firmware is from the 25 November team handover. The original source files were checked against the handover manifest. The CCS project name distinguishes it when both projects are imported. The LCD library retains its original credit.

In CCS select **Project → Import CCS Projects**, choose the relevant directory and build for MSP430F5529. From a PowerShell prompt in the repository root, use either command below. Both compile and link only.

```powershell
./Docking_Station/MSP430/build_station.ps1 -Variant standalone
./Docking_Station/MSP430/build_station.ps1 -Variant coordinated
```

The helper accepts `MSP430_CGT_ROOT` for the TI compiler directory and `MSP430_DEVICE_ROOT` for the CCS device-support directory containing `include` and `lib`. Each variant builds in its own directory. See the [station pin map](../Booster_Board/README.md) and [operating sequence](../README.md).
