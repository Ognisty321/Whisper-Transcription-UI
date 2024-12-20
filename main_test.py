import sys
import os
import subprocess
import logging
import configparser
import base64
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QComboBox,
    QLineEdit,
    QFileDialog,
    QListWidget,
    QProgressBar,
    QPushButton,
    QCheckBox,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QStyleFactory,
    QMessageBox,
    QFormLayout,
    QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QByteArray
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap

try:
    from PyQt6 import QtQuickControls2
    QtQuickControls2.QQuickStyle.setStyle("Material")
except ImportError:
    QApplication.setStyle(QStyleFactory.create('Fusion'))

base64_icon = (
    'iVBORw0KGgoAAAANSUhEUgAAAIAAAACACAYAAADDPmHLAAAACXBIWXMAAB2HAAAdhwGP5fFlAAAFAGlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPHg6eG1wbWV0YSB4bWxuczp4PSdhZG9iZTpuczptZXRhLyc+CiAgICAgICAgPHJkZjpSREYgeG1sbnM6cmRmPSdodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjJz4KCiAgICAgICAgPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9JycKICAgICAgICB4bWxuczpkYz0naHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8nPgogICAgICAgIDxkYzp0aXRsZT4KICAgICAgICA8cmRmOkFsdD4KICAgICAgICA8cmRmOmxpIHhtbDpsYW5nPSd4LWRlZmF1bHQnPkJleiB0eXR1xYJ1ICg2NCB4IDY0IHB4KSAtIDE8L3JkZjpsaT4KICAgICAgICA8L3JkZjpBbHQ+CiAgICAgICAgPC9kYzp0aXRsZT4KICAgICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KCiAgICAgICAgPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9JycKICAgICAgICB4bWxuczpBdHRyaWI9J2h0dHA6Ly9ucy5hdHRyaWJ1dGlvbi5jb20vYWRzLzEuMC8nPgogICAgICAgIDxBdHRyaWI6QWRzPgogICAgICAgIDxyZGY6U2VxPgogICAgICAgIDxyZGY6bGkgcmRmOnBhcnNlVHlwZT0nUmVzb3VyY2UnPgogICAgICAgIDxBdHRyaWI6Q3JlYXRlZD4yMDI0LTA2LTA4PC9BdHRyaWI6Q3JlYXRlZD4KICAgICAgICA8QXR0cmliOkV4dElkPmY2MzZlZTNjLTRkN2EtNGZmYS1hZmM5LWMwY2QxOGQ5MGM0ODwvQXR0cmliOkV4dElkPgogICAgICAgIDxBdHRyaWI6RmJJZD41MjUyNjU5MTQxNzk1ODA8L0F0dHJpYjpGYklkPgogICAgICAgIDxBdHRyaWI6VG91Y2hUeXBlPjI8L0F0dHJpYjpUb3VjaFR5cGU+CiAgICAgICAgPC9yZGY6bGk+CiAgICAgICAgPC9yZGY6U2VxPgogICAgICAgIDwvQXR0cmliOkFkcz4KICAgICAgICA8L3JkZjpEZXNjcmlwdGlvbj4KCiAgICAgICAgPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9JycKICAgICAgICB4bWxuczpwZGY9J2h0dHA6Ly9ucy5hZG9iZS5jb20vcGRmLzEuMy8nPgogICAgICAgIDxwZGY6QXV0aG9yPsWBdWthc3ogU2VuZGVyPC9wZGY6QXV0aG9yPgogICAgICAgIDwvcmRmOkRlc2NyaXB0aW9uPgoKICAgICAgICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0nJwogICAgICAgIHhtbG5zOnhtcD0naHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyc+CiAgICAgICAgPHhtcDpDcmVhdG9yVG9vbD5DYW52YSAoUmVuZGVyZXIpPC94bXA6Q3JlYXRvclRvb2w+CiAgICAgICAgPC9yZGY6RGVzY3JpcHRpb24+CiAgICAgICAgCiAgICAgICAgPC9yZGY6UkRGPgogICAgICAgIDwveDp4bXBtZXRhPtl0FtkAAC2pSURBVHic7X17cBzHeeevZ/aBN4gXQbxIkCAo8BWSokyJohxRTxKkosisuCJFVqL4Gcc6R1dx7uzEUVXKj1LFuVixlEtdKrYkJtL5LFeik+5sixZ1sWDJlChRFCxCFJ8gCRAgCQoA8dhd7E5/98dMz/T09OwOwKWkFPmhFrsz04+v+/v66+/R3cNwBS5rYB82Alfgw4UrDHCZwxUGuMzhCgNc5nCFAS5zuMIAlzlcYYDLHK4wwGUOVxjADx+V/qAPqqIPpMHLly83pqamkgCSnPM4ERlExEzTZAAYETEAjDEm4+R+i+fSffc3YwyGYYQ+V+85lURKCw7m/IFzzogIhmEwgSgAWJYVvTzNc1GUZVkWY2yaiEYrKyvPpFKp6RMnTnAn3SVjiEvCAOvXr2fnzp0rtyyrnojqGWMNABYAaABQSURxAAZjzAAgPizkY8BmAl0aAzZNA/d06aLck5httnkvqm4iAmxCcwDTjNEJGHjdZPHdZ8+efSOTyXBcAkYoKgN0dXWZqdRUrWXxJURYS0TXAVhHRIsBlEv1zaleaeDB6bBZ54sCYWUzxvI+k/Ky4DOCLitjbh6SBjsHKAsYMwDSAA4zxr5PRD8cGhpKo4iMUCwGYM3NzdWMYTWAW4loOxFWAEjaDZTrIdjNnkMl/k7+Dw5yGwThxTdJiQwAsADMADhiGMafDw4O/l8p8UXBRTNAc3NznIgWAbgDwD0ArQFYnIhsyczAQATO7YYREfzTcDh8kIT+4Ooipz7vjpAsto7BYJoxGIaQNgQwEMgQmWcYY//Lsqz/AuDcmTNnLgrxi2KAhQubSy0LazmnTwO4i4hqoYj58opyNDc1YX5jI6qrq1FWWoZ4PA5HefO+DQMGY5r7DAYzfPfVNL70jIEZhj3RKvfV/GH386YxnGfM8D3X1aMrPywt5xxTU1M4ffo0ent70dPTg0OHDoGIg4iLLhcSIQdgH+f8CwAOnDlzJjdXGs6ZAVpbW8sBuoFz/gDndCuApCjTMBiam1uwevVqrFy5Eks7l6KttQ01NTUoKytzGw1I87OYK9T7otA814E5nrFAw2aVf5b1z/ZaSBvBDOKefA0AR48exdNPP41nnnkGExMTmJmZAWPk6ArMAuiAYRgPZDIzr42MjGQDjYgAc2KAtra2EiL6uGVZXyOi3wTIEPN6fX0drrtuIzZv3oyPfexjWLhwIRKJhC8/SYRW7wOzV9oKgRCxxS53NqCbYgrhI/IMDw/j4YcfxgsvvICJiQmnLSCHCfYT4QEAbwwPD1uzxcucbYbW1tYYEa3inP8FEd0Cx6QxDAPLli3Dvffei/vu+33ccMMNqK+vh2kGq9CJxEvx0cGHwQRhjF0IF9GOiooKbN26Fc3Nzejt7cXk5CRsHYsYgHrGWDtjeG1ycvL92eI2KwZobm5mRNQI4L8S0ScAMgGwWMzEmjVr8cUv/jHuvPNOtLa2hhI5SsMvJXyYdYfVX0hCib7r6urCmjVr8Oabb2J0dNSZMZkJUD3AEtXVFb+amJjMzAafWTFARUVFKWPsk0T0JwBK4cz3q1atxpe//Ce45ZZbUFlZqW2A7veHAWG2/KXEK59Emg0ejDEsWLAAXV1d2LNnD8bHx537KAFYLcBOVlfPe/fChQuRLYPIDNDQ0GDE4/HFnPO/JqKFds1g7e3t+OIffwm33XY7SktLZ92ojwJ8UPjJErDQdOVTGiGZVoxh/vz5mDdvHn71q19hZibjPDIqAcQYo56JicnJqDgZUROaphknoh1EtFLgMq+6Bt3d223il5Ro833Y4j6KXvBB+hvmqpvIGCaTSXR3d2Pbtm3Cn8AASgC0hnN+82zwicQAixcvRjwer+Sc/77IY5oGOjs7cPfdd6OqSoj9oIPno+S1y4eLePZh4quahe59SL3qPC8vL8d9992HBQsanQcEAC0A29w6f35F1DojMUA6nUYul7ueiJYKfKqrq7FlSzfa29vtcBkYGIPzKTzqPigQHjY/+EUxlE6X04v86udSgsBLrUe+Mk0TixcvdqSAiD+wUoAt54bRFbWuSAwwNDTEANwFR2cwDAMNDQ3Yvn07DNNwkI5a5cVDFAKohHJ/27E3v2KKoKJWiNBhTFFs5lAlAeBNF+Xl5bj99i1IJksghQaaibF1UcuPRUxnEtFmUX8ymUBX13K0tLRA+NwutaMlMBoU2zpflI5zjlwuh5mZGViWhWw2C8uywDl38Y7FYjBjMcRjMSSTScTj8dC65bJ1OBXLoSWkABH5vJsCm1gshvb2dnR0dODgwXeddKgHoQv24Ob6kj2IwgCsqampjXPeymxAIpHEhg0bAk6eS+XJywcy48nMkE6nMT09jampKYyPj+PEiRM4efIkzpw5g/fffx8TExPIZrNgjCGZTGLevGrU1tahsbERzc3NqKurQ1VVFWpqalBdXY1EIlGQycMY4mL6w5sKCOQMN1vg267z8vJy/MZvrMGBA30wDMZAKAPQ0traWj4wMDBRqPxIEoBzfhVjnslomiaWLVsW8F9fKingE4OaES9+ZzIZXLhwASMjI+jt7cUrr7yCN954A/39/ZiengYRwTRNRT/xRDjn9ncikUB9fT2WLevEmjVrsWLFCixevBhtbW2ora31xTLCIMz3P/dO0E+ziUQCS5YsgWVZYCwGw4BBxCo559UAJlEgZByFAYgx1irfME0Tzc3N+sRFZAKV8GHzciaTwblz5/DOO+/gpz/9KV566SWcPn0ajNnRNiJCLBZzyxFle2WJyB8cRuA4d+4czp49i5df7kF5eTmWL1+OjRs34uqrr8bq1avR1NTkK1NW2tTfxeobX/nOPdM0UV9fL+IDApKwF+AUhKgSoEFedxeLxbQev0sJcueJjshmszh79iz27t2LZ555Bj09PZienoZhAIbh5bPDqQyJRAIlJSUoKUkiHk/ANE0QkasfpFIpZDIZWJbl1mcYBtLpNPbt24d9+/ahra0VN9xwAz7+8d/Exo0b0dDQEHB75/M0zkUauK5iOMtFpDIMw0BZWZlUHgOAOGMsqS/ND5EYIGaghEsOKaE06cy8Yox+nciX7xMRxsfHsX//fvzoRz/Cz372M1y4cMHBxyE6gNKSUtTX16Ourg41NTWor69DXV0d5s2bh/LyCsRiMXDOMTMzg8nJSYyPj2NsbAzvv/8+zpw9g+GhYYyNjTni1cbj1KkBPP30/8Qrr7yKm266Cd3d3diwYQMSiSQY8we6BK46X/9spYGbVipPVmCdRyKtyRiLRttItRsxkxHRpXaWRHHU5HI5DA4O4vnnn8dTTz2Fw4cP++Zz0zQwf/4CLFq0CB0dHVi9ejWWL1+O1tZWVFZWwjRNcM5dC0CeCjjnSKVSGBkZwcmTJ3H8+HEcO3YMhw4dwpEjRzDpeFgZYzh58iT+5V/+Gb29vdi+fTs++clPoqamxn2u+kHC9JjZDhhdesMw1GdiwW1BiMQAjDHG7TVdAOyOKjaoxNc1NJPJoO9AH3bu3Il/e/bfXILYhLf1klWrVmPjxo24/vrrsXDhQpimiWw2C845stksZmZmXPx1jp1YLIbGxkY0NTVhw4YNGB8fx9GjR3HgwAG8+eabeOutt3DhwgUAgGVx7Nu3D6dOncLhw4fxxS/+EZYs6fCt9lHbqEqDuTCBykya/GIpfUGI6geA5Gjw1qoVCQJ+Oo05NT09jddffx3/+I//iBdffNElImNAfX091q27GrfeeituvPFG1NfXu6M8l8u5v/MRXgXLstdWVFZWYt26dVi5ciWuu+467N+/H7t378bbb7+NdDoNxhhGRkbwr//6bxgeHsKDD/5nrF+/PhD4EcygI/hcpgM5j122ry2RYzwRJYCNp7i2LI6izgIhc779yCb+L3/5Szz22GN49dVX3WfxRBzLOpdh27Zt2LZtG9ra2lylTjh6ZHGvlhsdPUI8HsPSpR1oa2vFypUr0dPTg2effRZnzpwBESGbzeLll3swOjqKv/iLr+Paa68FEbnrBjnnWmtBrmOu+pNOAkANyoRAJEeQ4+d3+4yIXxLXr05xymQy2LNnD/7u7/4Or732mpu2oqICGzZswN333ION112H0tJSl+gy8bXuYKU+HR7BfAxEQDyeQFdXFxobG9HZ2YknnngCfX19juUA9Pb24i//8uv45je/iY99bENAY1fLv1gm8KYAL1xk345WTkRRQZykHpHUgYuGfC7dXC6HAwcO4LHHHvMRf968edi6dSv+05e/jM2bb0QymUQul0Mul0M2m3UlgOqrl8Wx+JimiVgs5vuIe6Zpuh91Xq+pqcH111+Pr371q9i0aZPkEzBw+PBhfP3rX8d7773nw0VmyDC/xlwUbFXXgLfDqXDeaFUwsj82SMuULxp0Zh5gK5pDQ0P4+7//e/T09Ljp5s2bh+3bt+Nzn/scVq9aBeIUILys4Ys6ZMLHYjHE43H3o17rPjJzCGZIJBJYtmwZvvKVr2Dz5s2IxWJOvcCRI0fxta99DWNjY27sQTCBHINQmWA2EkAnRZzfkaeAqMoCeX4GO7hSLB0wzLRMp9N44vEn8JOf/ESkREVFBW655Rbcf//96OjocEe9ILzoZBnUUS4TUxA3kUhoiK5nCllSCIZqaWnBn/3Zn+Haa691RyPnHAcOHMA3v/kNVxmNwgSFlFMdyEqgkzcyF0VmAEgkF46WYoBqLwN257300kvY+c87kcvZex4SiSSuueYafPrTn0Z7e3uA+KppyhjziXDdSFdFf7gECD6T0xuGgfr6ejz00EPo6Ohw2sIxM5PBz3/+Ip599llXN1GZQLVMCgGRf+wxZm9WUbsVxZYAkBmAk09zLyYQEUZGRvDd734Xo6OjAGwOb29vx+c//3l0dnbCsizfqFeJL496lWCqFBAMos75phnz/Q6bKmKxGGLxmOuTf/jhhx3XrD0qp6am8Oijj+Ls2bOBMLSO4PmcbfYtr+9dM1AogR7Jxe7jghCJAWz912MAXgTiqx0gz2dPPPEEent73QZWV1fjvvvuw7p168AV4qvzp0xQdXSrRNcRXqf8yd86porHvSlkyZIl+OpXv4pcznJ6zg4sPfbYYwDgMq/OE1nYEyotavH1mQh8eF0RlQ5RGIBAkh8YF+8J1Gm+zPk+fvw4Hn/8cbeORCKBTZs2Ydu2bWCMIecQXia+rOTJ4l7V7GWi6u6p+w1lhlDnfZ9eITNFPIa77roLmzZtgqBDOp3C7t270dfX53olVVNVxwShZiv574kYiJwUxZQApKwsKWYsgIgA5rXp8R88jpGREbdhNTU1+OxnP4Py8nLfnK8SXyaI+lv3kfUOWQ9RI3vyc0F4VWL4JE3MXkn00EMPOVaB3YMTExN46qmnAt5J1TxU+1fX16qloDEDi6sEMpB0OgUVPxZAdkOHh4bw7P9+1m10LBbDtm3bsGzZVQHbXiVamD2vG+FRCS5LA929MEZIJBJYvHgxfvd3f9dtYiqVwp49e3D8+HGfAhs2FcxmkCmOIOdWMR1BDB4DULSoXd7iNNEyxhiee/55nD9/3hVpYukzEflEpqhHECOfE0d2+oQRPFIXaBhHZQQZBwD4/Oc/j7KyMog4yvj4OH7605/6pgDVYRWlT91lLFIswEvD4EQCizsFMCY7gorvCczlcnjuuedcsw9guO22W9Hc3BIwmQA7PsEYAgSX52mZ8HaeYJ8UYgT1mcoIsgRSFcWmpiZs29btKnDT09PY86s9mJ6aCsQrdEwQ6iVUFF8bR1/a4k4BRMxVQe0jlML9AHPxZRMR+vr6cPToUScKZ4/4e+75PZ/p5M9nwDD8mrpuxEcd7ar4j9IWNa2KCxHh937vXhiGCYAhl8vh9NBp9L3bF1AE8ymDKo5C4/O5laV0ths42jQd1Q/giwU4tUTM6gcdlzPG0NPTg0zG3tjKGEN7eztWrlwJIh5q7qmiXx35usWbeRmC2QavN9AKz8VhU4OwRlasWIHOzk4Q2XSbnp7E66+/DgA+P4Yat8hbn3LPcBxBtvff9QQW0Q/AQILJfKXOkgfUaJfc0D179jgnYNiu5q1bt2rDuAB8nRyF6CoOOoWLXMr7wh6iB4A8jCNLAVUviMfj2LJli9MWIJVKo6+vz1UAw8xBGTe5Dn29BkC+k7hY1LE9e0+gzw8ZMbeuQIkAFy5cQH9/vysBcjkLt912my+IIir2zD7D+YSLfRnCrnVzur9hTHGyOXnFR1Oeis+NN97oJp2ZyeL06SGcP38+dM1CPg+hDvznZIJQbE8gZAYQwaYirgc4cuSIdPQJQ3V1FTo6OqQR4FXvja4YDCNcyweC4l53rQMmPwtpqk7G6vwGsVgMnZ2dqKmpcfWdyckJHDt2LBC9DJMEhUB4AiURHZk6EZeEyQsAbI0zzBeginndc7sUBqFK9vf3I5fL2ad7MYYlS5YgkUggm81KDOARL5/oT6fTGB0dRSqVCsyr6lyb75pzDk72knLihOrqarS3t6OiIv/GW0FkYZoZhoHKykrU1tbiwoVJGAYwMTGJ3bt3o6OjA/X19bAsy1Ua5T6K2reae8VmADExur4gZxeNJwWjc6zNQOTsyBkYGMAzzzyDsbExW5QxhrKyMliWMPu4m08QP8yxQ0TYu3cvdu7cif7+fg958sKu8j0Vb/38azPfokWLcP/99+Pmm2+elUUhJFZ9fQMGBgZBZCCTyaC3t9dh0qAVIDu78ukAan1KJ0diglkwgHTCoaOo6RVpfb2k+QXYcYXz58+Dc454zD4/cNGidmnu92xcWcTrlD7LstDT04Of/exnEZsVDRgDBgYGsGLFCmzevNl19BRierEW0DAMbNq0CW+99ZaLbzKZREVFBYjg0wNEepkJCuMXSFPcRaFQwsGA03hBn3wZRSNEZ3kiAwBQV2dv1hDr9QHg+uuvB+eWm0znfZNHv7zWbsGCBWhpaXGXbqvzvdxZ+e5516LcJnR2LnVHpZxXYzO4XSPSdXd340c/+hHOnz+PZDKJq65ahqqqKrePZjP/q9JLxZlYsSUAl5VAu1zOeeDsmjCu9dnw4p6Tp6KiAtdccw1+/etfY2xsDMuXL8f69Vc7o4C7UsAT9XptnzF7h8ztt9+OZDKJU6dOaSWFyjhh91TbvqmpCWvXrvUFXnyMo3SZywRO/iVLluCOO+7A97//fcybNw/XXXcd7ONgg6ap6DO5LwNMl59Jiq0DGJJ7xEOwELhpAp5Kf5p169bhxz/+Mc6dO4cdO3agvLwMUM4V9oiZ37vX1taGe++9N1qzigQqFuoIJRAM00Dn0k4Q2buX7A2dzlMKfgBoiT8LlIqpA3ByVXZxJ0QHiAJi335ZWRmSySQSiQQaGxuRyWQwb948WBbH2bPDzv4Du0PEjp2SkpK8/v2hoSG8/fbbGBkZCdjYqpjNd63maWpqwo033oiOjg5ffTYNPQJNTU3h5MmTrlMLACxuYWHbQlRVV2Hx4nbU19ejtLQUjDGkUmmMjo5hwYJGxONxrSLoq08ZeCHMcUl0gEDFeTlTnvMlpEdHR9HT04Pe3l7ceuutWL58ORobG3HvvfdicnISXV1dmJycwhNPPIl0Ou3WFYvFsGrVKtx9992uFSCeCZFoWRZefvkXePTRRzE8POzgGIaeztceloahvr4eMzMzWLx4sS7+7jq0Hnnku9i7dy9mZrJuH1mWhX/6p3/C2rVr8d3vPoJYLI4FCxqRSCTw7rvv4tvf/jbWr1+Pz3zmM2hqagpIOLWtfpx1A4EYIjLBRVkBOnDFlkJ4AW+88Qa+973v4dixY1i8eDGuuuoqNDQ04LbbbgNjDJZlob+/H7t378bU1JSv3Ndeew0bNmzAypUrtR1hWRYGBgbQ398PsXQ94vL4kLYI/A2MjIxgeHjYKVPP+H19fdi9+yUcPXrEVV4B2zoxDAM1NTWYP3++y5ic204g4QXt6urCjh07kM1m3XqEf6BQVFNiysjiH7hIKyCvGiA7CSQYGBjA8PCw6yUrKSnxzXmcc/d8HlUJSqdTGBwcdE8nER85Crdu3dW4/fYtGBo6HVAgRR3qt3pPdKZwsRqGgUWLFmHr1q0ePpomj4+PI51Ow7K4j0hEhHg8jpKSEt99zjmSySQ455icnMTIyAiy2WzAzBTtFMqsjKsA5TqyK3jODKBKgKiOICJyN3EAcM/ekZ8LrhcbNG1GALLZOLLZrOsh1DHB+vXr0djYiPfft89NDtPs893XPS8vL8f8+fO1o09o+wLnXC4L4Z4VkskwDPc9CXIfmqbpbmzJZDLIZDLuLiMB4iyGsGlX4Or2IhXfEcQlz61dR2TPH3x6gGiIYCDVrBKbKIEgk4nDHDKZNDhPaG3m0tJStLW1oa6uzleWi7Nku+quZYkjf1dUVASOvVfBywN448XTA2TmEnXJTh9xUom3kTQYvxD9JH+7/eoRqPhTAAMjmQN0GzFUYuisP3UEhCmRqsNFpJ+ZmUE6nZbqIrejDMNwTw05ceKEp8kTt13Xkn+fE4G4/YycZ7I1IH8DQEtLC/7gD/4A27dv93eMgnPYaizRlrCpSEjGTCbjegNFeSrjhCqD5GOASzsFEFHBGlwNXUXUAZ5nj6FW1BK5DCAHiOzOsiNr+/fvx7PP/qujQHr94A505jXE89gxewkA89clOtwwDAwNDWHp0qXYsmWLX0QrksJGW+T1aBKYMp3Ewq8ht01MaaZputOHzk8g95VhGLAst44im4EMFLA/OY8saGRJ4GMAK9yS8EaI14m2IpjG9HQKgKcU2QwgFoeaIAIsK8Czfvyh8d6FMB3nHGVlZSgvL3f1E63EY369V8VdB/ZyMYDI3komDp1QVzar6wVUKcD8FTNWZAkA+HqzoCsyLKNn0yK/zzvM1s5kMkinUzBN53RP0967R2R35ObNN6G8vAInT560Mc2j5OVT+gQO4n5zczM2bNjgw0X0hRjxAQ6QQGc2y7ECMQWk02lXYRT7EoVLXDf6tf1FiHZAEGajBAqnFwAGKrg9TDdCxH1XycszBYQxgC0mM4jH7fX3iYRYW28/b2howO233+7G2MOILXCR8ZLxU01CmUFkfOQoOYP9NjEdBHQmeNaDKEucYRSPx5HLZWFZYgNJOPFVt7FUfBElAAMxRkTkCRbi+vV63rwv/OASSuQnLPnWmfgthTBxbJuBM8hmSwJLqkSasbExDA0NBfBTr+U86nPZiwcADQ0N6OrqQon0XgQGv69LaO7eU68HwhxnnpfPXgo3MzODZDLproewmdvblqHrl0B/MRh0SZVAVtgTGLABKPhclgCqxRAmAWybWWwOFce7es///d//Hd/5zl9jcHDQN3J0fn9B8KBFIzs97c6tq6vD5z73Ofzpn35FTujjALtpegkQYMZAf5FvC7kn1fKXE9JfLOrerbkxAIXvEM4bH0AeCeCATjzL4F9FK39s6TA4OIBjx44FOk4uX4jzMJBNTNvSsANYx4/3I5vN+hwz/rKNMBXAZThFWfNJgODKIGlDVgFGuLRTgCLJBbfOBVxEKbyMMAIFRbrfJW3vxmlGY2MjTp701gPkU/DUZ+q1CEHX1zdg3bp10qmcfsdWyFwcirtogG9AaBU9VcLowedQs+2A4loBJE/qTPKiKSCLtDBEPSUwXJEM0wFk8S3b3iL5zTffjHXr1jlTAPfVp3WeKL9lpU++V11djba2tiCivikgfAdSPiVQNe/Eb1G8/VvfVyFtMwwjeGyIDiIyAAtgwEP8AJ6Y0/kB/YhSHikyq5FkP4Ewx2pra1FTUxMYXfLvYEfrd+eK3+pp47py800tWrx96aMdFBEGticQgibFdgWzgDoii94AInYK75505fcEhnO1PDfKdQZBdJzNdBcuXMDbb7+No0ePuiNH9sbppIj6URVEIkJNTQ1uuukmrFmzRqo5iHc+CRBAn+TYA+AtgZNLj0ZLH7MDDOCX1hVsi7Q8nCq0fiJ7bYBsBtoekLwSQICiaOdlAs45XnnlFfz5n38NExMT0jNgFoNCqd/OV1paiv7+fvzt3/6t5/TRiH8/A3jPw/rLL6XUfATGxHsAgnqd7BG06yUpTTQpMucVQVqO1mXUzLtiU4g8L6qEzael+8pXmEOEme2Yuiz2L44BxMEPIoSra3weR6Be4dU4l2Qie+YtIE8ROvz8nkACUFQdICQYlE8H0KsAngSA3hMo8uumAPFc/pZHhmmaWL68C3fe+ds4fPiwW59p+iNrhmnAYAaYwYLfhveMwduFVFtbiy1btriLNcJAPqW9oORSzEK9ssegG/3BepkU8GIIZ0U/RGIAxwIITgH5dAByfOTeE3t1rGG40TfifvNJ7iRPG/d3ZFCTt8sWHdTZuQzf+MY3MDMz45ZTyCJSbXNXiEoEijlvE5Ndt7pyCvkBVFAlnVCg1dFfCH+7X/2382ZyIKIECLKm7QfPh5RkwoS4eQUTyYGhfPZ0WHxBRi2bzeLChQvuGYNymWFKXz5FUOStqKjAVVdd5b4qR8cI9hTgvy+mBd0pJ4Vc1V7bCjOwEgwCFfd9AV7EQ6AYJgH0EBzZBPtYmGwu60upesxEnzDm71QXH0lxIiIMDg7imWeewcGDB7WdrTPxZGtBeOD8DhmG6upqbN++HZ/61Kc83IL9FN4D5MUV1LaqpqT8LZUQWraTQWKV6FrvrCSAPK0TBbYKBHPAm5tETnF+DsiLfskg/OFhYlusq/O/EUWssuU4ePAgnnzySXdl7WzAX6VfxxB433PPPW6UEeScb8i8hSMivq+WJ1b7qL6JrHsmktw2ppShmoZBMIKKZPEYgGn8APmWc7k4UBDlhoYGrFixAnv37oVlWb7lXWI0zMzM+Fy4cHSH2tp5WLBggXM2gJjb/TVUVlaiubkJp08PgSBetYhAd8gHrei6VR5PjDFUVVVhxYoVetHvKEktLa1obm7Gvn37YFneYVecc2QyGd+KX8A5NdQ5BKO8vAyrVq0M7HsMdqoefExjl13EdwbZRpRPZw/6rKNBZ2cnvvCFL6C1tRVLly71Hf4ofk9PT2PVqlWorq6262f2ypmWlha0trYikUg4K2UMCI+nncZAV1cX/uTBB3Hq1AAM4cs3DTCxesjV+iWNXyhRhgGDscC3YRioqKhAV1dXQGmTZ+impiY88MADuP766zE+Pg7Oubvit7+/Hz//+c/dFc2WZeHjH/84GGP41Kfuxfz589Ha2uaecipWOeULMPlo5FNkbV9wFHpEXxGkDDZdJA+QNGdvrvDJwmQyiU2bNuHaa691l0GLUZ9KpZBKpZBOp9Hd3e2+w0/M5WKJlDje3WYAMVrs8uvq6nDXb9/lEVUeSaqTJo91EWh+yHO5W+LxOFatWoWFCxcinU47i1dSmJ5OYf/+/di1axempqbAmH1i2PLly5FIJLBu3dXO4paEywDe7ifZBMwzBSj0tiwrv73qQGQ/gCPlXHTyreaBSCgzgVqYZO/LByqJeDgA91owAGPMXSqVTCYRi8Xdo2KEjS/K14lSj4a6Do3mKApo7spzwzBQXl6ORCKBTCbjEDSOrq4uJJNJnD9/HkT2yqUFCxZgamoKlZWV7kYZ+8XVwZdTFAJfGgJMZrJwq8mDaH6AEE9gPsVUOCTC7WXmY4B4PO6Lh4sNE7LpxJh3PJwYMYIJZAYo2B7yAlayxREJZMZ2fR5+LV4wn8zUdXV16O7uxs6dOzE9PY3PfObTKC0thWEwlJWVunpNIpFwmFtmAMPFV4uSkHbyfGSClZeXs8nJybwcEJUBpC/RZr0NEPRs6Z+rHSVetwLAHQ3y6FclhnwEvG6Hj7YdIZ45ne9ByxginfOfNENDZWzBrIwxpFIpV4otW7YMyWQJTNNEeXkpGDN97bKnuOBxOPp2SbgKJiBiYotdPphNOBhya6MsCAljBrWT/LF973Qt9fg0wDsjUD0XOFxzDserkNNJc9MJbjmXsF3eXp9TgLFlx1Jvby9yuRwWLlyI+voGd+GqvWfQPxXa0i0oBXRMrm03cWZG6IxZrgcIjhoVwkSqPB/JDCB3lHhmb3LwXq2iliPnk7/zLf7Q3RM4uW1hrKAmQPI/UReCDK4y9i9+8QsMDAxgZmYGW7du9QWWhIs5TLqpEk7XpwHrhIEZscKGwNyDQZwjeDpOYW1agNjtItvFYaNHLV9lIJUJCjGCDl8STh2NV07JYH9Jt1RJIreNc46RkRH84Ac/wPj4GOrqarF161aUlpa6S8CFA8gwGMT5x+oRuLol7rp2eDgxkBqK1UDEYBAFHUEhsYCoSpUgoOgo0Sj1lCw1WCR3svhWCS9/ZqPkqYRUF4Wo4FuHpyGIIP5f/dVf4eDBg2DMwBe+8Eeoq6tzlUN1CpOtonzvO1Dr8t+zHbeseFMABVYz2P7yYMqoxBeEkU8HE52mEj+sDACBjlGVpSj4hAVlBgcH8cADD+DQoUPSMfYe1NbW4nd+53fwh3/4h+6JX8KVnclk8Oabb+KRRx5Bb28vDMPAXXfdhe7ubpSVlbmMLhREuR0y0XWnoOsgeD+aPhT13cEBpX8ubw9V7VKZiOKZPPoFCGYJyyuuZQbQTR35kUNAo//sZz+LAwfeccoK5k+lUvjhD38I0zTR3d0Ny7IwPj6OgwcPYteuXdi7dy9SqRQqKyuxZcsWfOlLX3LOQLJ8xJXx1o163bSWZwog6V6xpgDGZU+wTjmbLeiUQjUkLBM+jAF0c71IH1X0q0Bkv+7tvfdERFGOQhqu5CMiDA8P42/+5jv4znf+Grbf336HcCKRQFlZGTo6OrBjxw584hOfQFVVlRvosiwLiUTCJ/plJVAlvMroKr7+ewyMwSqaBAB4DoBPBgonja7zonZ8WLq5Ek7OO+syKMw8dI086KQAY0BJSZlzepmtxCWTSdTX1+Oaa67BHXfcgcWLFwckGxG5R+Gool6WCoVGPgD3UAkljJ6OEquJuiIoTYSU6AXOOVKpaddUm3VnC3saShRLI7pnC4W04/CMHokZY85JIwtx5MhhCAmgW2NRWVmFG264Addccw0Ys885bmlpwcKFC92DpUXwR1YqhfWjs2byEV/XR5OTk4EQOhGf5BHm6Yg6gDEJ0ITs1Hj//VFkMhnnpUh+KMQUmulWqmvuo/+iynJse2E5GYaBBx98EA8//DAymYwj/v0j0DRNrFixAjt27MCSJUt8plwsZruyVc1dPhpHFf+qBaNTZnW6zfDwsHukntMYizHjvGmaBefpqGbgGBGdF9eGYeD06dOYnJxETU2NDxl1/lbKCTybkwQJx3PWpp8PGPPt2LnzzjuxbNky3xs+uMWRs+zwdTKZxKJFi1BbW+uuYbC9lGLEcu2oVc0+VYENI774rTLB0aNHMTExYaeznTPnAbxfWVnJh4aG8jY5qiPoPECDAMsCiBuGwQ4ePIhzIyP67VIhUIhBLhbmPP/LuCl5Ozo60N7e7q5eEt/it1jHIPILS0a4scXcL+pQtX4dI8xGgZ2amsKhQ4cwPj4OV64y1sc5nz506FDBKSDSooFUKpUB0A9gWNRy6NAhDA4OBta5uYiHzOdy41St/8OEMBx0I5ExwNtCHjy7R3dPdfCodn+Yo0e9Vs3jgwcP4vjx42JpHTECGOhVgE9HaXckBhgbGyPGjPcAHALAiMQ78H6Fs2fP6jNFIO7FjNhigo4p1efi2yaU6XPZhr2gUhXv+e6pkkCtWwe5XA49PT04fvy4hz8wTYRfMsamQjNKEPk0KdM03wWwH7Y5SIZh4Cc/+QmOHDkS6q8XUKhTPyqQT/SqnjnxxnCxLkFezaN7Z7GOOcKUPxkfFT8Z3vn1O3j1lVcxNjYGxlz/7x7G2NF4vCTSqthIy4YAIJfLzSSTySoAawDUA4xNTk4gkYhjxYqVqKqqKojwR4nYFwNinledN14kLwbT9AdyPOL73zSqMoWAQnrA2NgYnn76aezatcs5mRwAkGOM/TfDMF49efJUcRkgm82iqqrqPIAOAGsBMMMw2HvvvYfOzk50dHRoT9IsxARRpogPE3RatyrCg8Eb/YurvelDPw2o5at1CshkMnj++efxzzt34pz9pnVn9OP/Aez7hmEOijemFILIDAAAExMTU5WVlTEAKwHMZ8zWB37963fQ1dWFlpYW9/iUMORnAx8FBpBBFtPhxDcDYVzdugX1o9YhX8uQzWbx4osv4h/+4R9w7PhxSB6VMQDfIaJfnj59OvKmiFkxAACUlJScMk2zAfZUUEIENjExgb6+PixZssRZt29qmcC2U71PFAIX0iVgc2HAfJstRNVTwhQ4HTPke6WtztOnKoAqpFIpvPDCC3jkkUdw+PBhx/sHAogzhv/BGJ7KZq3R6elIBgCAOTDA9PR0tqqqaghAC8CWwvYlsPPnR/DWW/vQ0DAf8+fP9x2N7utA6SMcLj7G0IAshvPZyWo6wO/Xj2Juhkkv3eiXTbgwpS9M8dM5gMKAiDAyMoInn3wSjz76KE6ePAmLW0L0gzH2fxgzvmdZ2aPnzp2flU09awYAgImJiZGqqqoRAIsAtACIAYyNj4+hp+dlEHGUl1e4r4QRjXA8VS4w6b5gikLg66gCTCO+dUQM+6h51LIABIiqEjxs1IeZhzocRL9MTU1h165d+Na3voXnn38Oo6Ojzq4se4keY+xlxti3AbwxNHR21iHai5KbTU1N3QD+lIg2Aih1VqGAc45Vq1bjt37rt7B27Vq0tLSgtrYWlZWVgbPwiwEfpCNpLs6r2ehERPZBl++99x5eeeUV7Nr1Ao4dO4ZsdkYsShEVE2OshzH2EIBfDg4OzSk+f9FaVlNT0y0AHiCimwBUMkbusOSc0NbWhvXr17v6QXl5GQzDPmGDCM5R7lw6ut0+yl13nk/Yt8grAi3B5+KY+JAy1DoFLpI3z8NHxktcQ0mTH3/x27tPILKQycxgYmICo6OjmJ6ehv1WUUs6BZyEyE8D7FkifHNoaKjvYuhXFDW7qalpHYD7AWwnooWMIWYzqsEYY24oNJFIoKy0BPFEwj1Tl9wzfABxVoAMYcu1xO+wyGK+fGFlFSrDRVL7TK9j2PfkesLrsKO32sU25JTBAZwA8Khpxh4fGBgY1yA4KyiandXS0lLPOb8TwHYAGwHMh+dpdOsR03Z0CfrRMAX9xJV/R8dPSH5yF5+oTKqtwAJgMYYRAD/mnP778PDw4UDmOUKxe5c1NzcvJ6KbGWMbiGgNgCUAyqAwAaANvjkPfOkCqH7AwaNLXVmAsxiDBdvlnmaMvQOw5wzDeO7UqVPHio3TpRpeRktLy0IiWs0572CMLQKwAEADwCoBJBgjA66EcNFw5KUtN51FQyQxDDkKFCkfkCdrpQkFgPP6ccdX7saoJG2bpGux2k+Swe6OO7VctW63XHHNvPfOOXW4a47IyWUBZBEoy4AZACnAGAdwCsCReDzed+LECTmgX3Rm/CDkq9Hc3FzLOa9jjM1jjJURkekwgBjrojO5TWTi4jcAbnckkb041Q16iN8cADnLn9zn8m/GwJkXrieHMBx2oXJZggGdayIn+Ol7Ts4pzg5wzjlZlkWZTIZSqdTFEknkZ8r1JYGPxgR7BT40uMIAlzlcYYDLHK4wwGUOVxjgMocrDHCZwxUGuMzhCgNc5nCFAS5zuMIAlzn8f7gXPijUzHxyAAAAAElFTkSuQmCC'
)

SUPPORTED_LANGUAGES = [
    "Auto Detect", "Arabic", "Bengali", "Cantonese", "Catalan", "Chinese", "Czech", "Danish", "Dutch", "English",
    "Finnish", "French", "German", "Greek", "Haitian Creole", "Hebrew", "Hindi", "Hungarian", "Indonesian", "Italian",
    "Japanese", "Korean", "Norwegian", "Polish", "Portuguese", "Romanian", "Russian", "Slovak", "Slovenian", "Spanish",
    "Swedish", "Tagalog", "Thai", "Turkish", "Ukrainian", "Urdu", "Vietnamese"
]

WHISPER_MODELS = [
    "base", "base.en", "small", "small.en", "medium", "medium.en",
    "large", "large-v2", "large-v3", "large-v3-turbo", "distil-large-v2", "distil-large-v3"
]

TASK_OPTIONS = ["transcribe", "translate"]
OUTPUT_FORMAT_OPTIONS = ["txt", "vtt", "srt", "tsv", "json", "all"]
VAD_METHOD_OPTIONS = [
    "silero_v3", "silero_v4", "silero_v5", "silero_v4_fw",
    "silero_v5_fw", "pyannote_v3", "pyannote_onnx_v3",
    "auditok", "webrtc"
]
COMPUTE_TYPE_OPTIONS = [
    "default", "auto", "int8", "int8_float16", "int8_float32", "int8_bfloat16",
    "int16", "float16", "float32", "bfloat16"
]
DIARIZE_METHOD_OPTIONS = ["pyannote_v3.0", "pyannote_v3.1", "reverb_v1", "reverb_v2"]

DEFAULT_VALUES = {
    "language": "Auto Detect",
    "model": "large-v2",
    "task": "transcribe",
    "output_dir": "",
    "vad_method": "pyannote_v3",
    "compute_type": "auto",
    "temperature": "0.0",
    "beam_size": "5",
    "best_of": "5",
    "mdx_chunk": "15",
    "mdx_device": "cuda",
    "exe_path": ""
}

CONFIG_FILE = "config.ini"


class AppConfig:
    def __init__(self, config_file="config.ini", default_values=None):
        self.config_file = config_file
        self.default_values = default_values or {}
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.config['Settings'] = self.default_values
            self.save_config()

    def save_config(self, widget_dict=None):
        if widget_dict:
            selected_formats = []
            for fmt in widget_dict['output_formats']:
                if widget_dict['output_formats'][fmt].isChecked():
                    selected_formats.append(fmt)
            output_format_str = " ".join(selected_formats) if selected_formats else "txt"

            # Validate ignore_dupe_prompt as int
            ignore_dupe_prompt_val = widget_dict['ignore_dupe_prompt'].text().strip()
            if ignore_dupe_prompt_val == '':
                ignore_dupe_prompt_val = '2'
            else:
                try:
                    int(ignore_dupe_prompt_val)
                except ValueError:
                    ignore_dupe_prompt_val = '2'

            settings_dict = {
                'language': widget_dict['language'].currentText(),
                'model': widget_dict['model'].currentText(),
                'task': widget_dict['task'].currentText(),
                'output_format': output_format_str,
                'output_dir': widget_dict['output_dir'].text(),
                'vad_filter': str(widget_dict['vad_filter'].isChecked()),
                'vad_method': widget_dict['vad_method'].currentText(),
                'word_timestamps': str(widget_dict['word_timestamps'].isChecked()),
                'temperature': widget_dict['temperature'].text(),
                'beam_size': widget_dict['beam_size'].text(),
                'best_of': widget_dict['best_of'].text(),
                'mdx_chunk': widget_dict['mdx_chunk'].text(),
                'mdx_device': widget_dict['mdx_device'].text(),
                'compute_type': widget_dict['compute_type'].currentText(),
                'ff_mdx_kim2': str(widget_dict['ff_mdx_kim2'].isChecked()),
                'enable_logging': str(widget_dict['enable_logging'].isChecked()),
                'sentence': str(widget_dict['sentence'].isChecked()),
                'exe_path': widget_dict['exe_path'].text() if 'exe_path' in widget_dict else self.default_values['exe_path'],
                'diarize': str(widget_dict['diarize'].isChecked()),
                'diarize_method': widget_dict['diarize_method'].currentText(),
                'num_speakers': widget_dict['num_speakers'].text(),
                'min_speakers': widget_dict['min_speakers'].text(),
                'max_speakers': widget_dict['max_speakers'].text(),
                'diarize_dump': widget_dict['diarize_dump'].text(),
                'hotwords': widget_dict['hotwords'].text(),
                'rehot': str(widget_dict['rehot'].isChecked()),
                'ignore_dupe_prompt': ignore_dupe_prompt_val,
                'multilingual': str(widget_dict['multilingual'].isChecked()),
                'batch_size': widget_dict['batch_size'].text(),
                'batched': str(widget_dict['batched'].isChecked()),
                'unmerged': str(widget_dict['unmerged'].isChecked()),
                'window_geometry': self.config['Settings'].get('window_geometry', ''),

                # Add all newly introduced fields here
                'language_detection_threshold': widget_dict['language_detection_threshold'].text(),
                'language_detection_segments': widget_dict['language_detection_segments'].text(),
                'patience': widget_dict['patience'].text(),
                'length_penalty': widget_dict['length_penalty'].text(),
                'repetition_penalty': widget_dict['repetition_penalty'].text(),
                'no_repeat_ngram_size': widget_dict['no_repeat_ngram_size'].text(),
                'suppress_blank': str(widget_dict['suppress_blank'].isChecked()),
                'suppress_tokens': widget_dict['suppress_tokens'].text(),
                'initial_prompt': widget_dict['initial_prompt'].text(),
                'prefix': widget_dict['prefix'].text(),
                'condition_on_previous_text': str(widget_dict['condition_on_previous_text'].isChecked()),
                'prompt_reset_on_temperature': widget_dict['prompt_reset_on_temperature'].text(),
                'without_timestamps': str(widget_dict['without_timestamps'].isChecked()),
                'max_initial_timestamp': widget_dict['max_initial_timestamp'].text(),
                'temperature_increment_on_fallback': widget_dict['temperature_increment_on_fallback'].text(),
                'compression_ratio_threshold': widget_dict['compression_ratio_threshold'].text(),
                'logprob_threshold': widget_dict['logprob_threshold'].text(),
                'no_speech_threshold': widget_dict['no_speech_threshold'].text(),
                'highlight_words': str(widget_dict['highlight_words'].isChecked()),
                'prepend_punctuations': widget_dict['prepend_punctuations'].text(),
                'append_punctuations': widget_dict['append_punctuations'].text(),
                'threads': widget_dict['threads'].text(),
                'vad_threshold': widget_dict['vad_threshold'].text(),
                'vad_min_speech_duration_ms': widget_dict['vad_min_speech_duration_ms'].text(),
                'vad_max_speech_duration_s': widget_dict['vad_max_speech_duration_s'].text(),
                'vad_min_silence_duration_ms': widget_dict['vad_min_silence_duration_ms'].text(),
                'vad_speech_pad_ms': widget_dict['vad_speech_pad_ms'].text(),
                'vad_window_size_samples': widget_dict['vad_window_size_samples'].text(),
                'vad_dump': str(widget_dict['vad_dump'].isChecked()),
                'vad_dump_aud': str(widget_dict['vad_dump_aud'].isChecked()),
                'vad_device': widget_dict['vad_device'].text(),
                'hallucination_silence_threshold': widget_dict['hallucination_silence_threshold'].text(),
                'hallucination_silence_th_temp': widget_dict['hallucination_silence_th_temp'].currentText(),
                'clip_timestamps': widget_dict['clip_timestamps'].text(),
                'max_new_tokens': widget_dict['max_new_tokens'].text(),
                'chunk_length': widget_dict['chunk_length'].text(),
                'postfix': str(widget_dict['postfix'].isChecked()),
                'skip': str(widget_dict['skip'].isChecked()),
                'beep_off': str(widget_dict['beep_off'].isChecked()),
                'check_files': str(widget_dict['check_files'].isChecked()),
                'alt_writer_off': str(widget_dict['alt_writer_off'].isChecked()),
                'hallucinations_list_off': str(widget_dict['hallucinations_list_off'].isChecked()),
                'v3_offsets_off': str(widget_dict['v3_offsets_off'].isChecked()),
                'prompt_reset_on_no_end': widget_dict['prompt_reset_on_no_end'].currentText(),
                'one_word': widget_dict['one_word'].currentText(),
                'standard': str(widget_dict['standard'].isChecked()),
                'standard_asia': str(widget_dict['standard_asia'].isChecked()),
                'max_comma': widget_dict['max_comma'].text(),
                'max_comma_cent': widget_dict['max_comma_cent'].currentText(),
                'max_gap': widget_dict['max_gap'].text(),
                'max_line_width': widget_dict['max_line_width'].text(),
                'max_line_count': widget_dict['max_line_count'].text(),
                'min_dist_to_end': widget_dict['min_dist_to_end'].currentText(),
                'ff_dump': str(widget_dict['ff_dump'].isChecked()),
                'ff_track': widget_dict['ff_track'].currentText(),
                'ff_fc': str(widget_dict['ff_fc'].isChecked()),
                'ff_mp3': str(widget_dict['ff_mp3'].isChecked()),
                'ff_sync': str(widget_dict['ff_sync'].isChecked()),
                'ff_rnndn_sh': str(widget_dict['ff_rnndn_sh'].isChecked()),
                'ff_rnndn_xiph': str(widget_dict['ff_rnndn_xiph'].isChecked()),
                'ff_fftdn': widget_dict['ff_fftdn'].text(),
                'ff_tempo': widget_dict['ff_tempo'].text(),
                'ff_gate': str(widget_dict['ff_gate'].isChecked()),
                'ff_speechnorm': str(widget_dict['ff_speechnorm'].isChecked()),
                'ff_loudnorm': str(widget_dict['ff_loudnorm'].isChecked()),
                'ff_silence_suppress': widget_dict['ff_silence_suppress'].text(),
                'ff_lowhighpass': str(widget_dict['ff_lowhighpass'].isChecked()),
                'diarize_device': widget_dict['diarize_device'].text(),
                'diarize_threads': widget_dict['diarize_threads'].text(),
                'speaker': widget_dict['speaker'].text(),
            }

            self.config['Settings'] = settings_dict
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    def get(self, section, option, fallback=None):
        return self.config.get(section, option, fallback=fallback)

    def get_boolean(self, section, option, fallback=None):
        return self.config.getboolean(section, option, fallback=fallback)


config = AppConfig(config_file=CONFIG_FILE, default_values={
    'language': DEFAULT_VALUES['language'],
    'model': DEFAULT_VALUES['model'],
    'task': DEFAULT_VALUES['task'],
    'output_format': 'txt',
    'output_dir': DEFAULT_VALUES['output_dir'],
    'vad_filter': 'True',
    'vad_method': DEFAULT_VALUES['vad_method'],
    'word_timestamps': 'True',
    'temperature': DEFAULT_VALUES['temperature'],
    'beam_size': DEFAULT_VALUES['beam_size'],
    'best_of': DEFAULT_VALUES['best_of'],
    'sentence': 'False',
    'ff_mdx_kim2': 'True',
    'mdx_chunk': DEFAULT_VALUES['mdx_chunk'],
    'mdx_device': DEFAULT_VALUES['mdx_device'],
    'compute_type': DEFAULT_VALUES['compute_type'],
    'enable_logging': 'True',
    'exe_path': DEFAULT_VALUES['exe_path'],
    'diarize': 'False',
    'diarize_method': DIARIZE_METHOD_OPTIONS[0],
    'num_speakers': '',
    'min_speakers': '',
    'max_speakers': '',
    'diarize_dump': '',
    'hotwords': '',
    'rehot': 'False',
    'ignore_dupe_prompt': '2',
    'multilingual': 'False',
    'batch_size': '',
    'batched': 'False',
    'unmerged': 'False',
    'window_geometry': '',

    # Additional defaults for new fields
    'language_detection_threshold': '0.5',
    'language_detection_segments': '1',
    'patience': '2.0',
    'length_penalty': '1.0',
    'repetition_penalty': '1.0',
    'no_repeat_ngram_size': '0',
    'suppress_blank': 'True',
    'suppress_tokens': '-1',
    'initial_prompt': 'auto',
    'prefix': '',
    'condition_on_previous_text': 'True',
    'prompt_reset_on_temperature': '0.5',
    'without_timestamps': 'False',
    'max_initial_timestamp': '1.0',
    'temperature_increment_on_fallback': '0.2',
    'compression_ratio_threshold': '2.4',
    'logprob_threshold': '-1.0',
    'no_speech_threshold': '0.6',
    'highlight_words': 'False',
    'prepend_punctuations': "'“¿([{-)",
    'append_punctuations': "'.。,，!！?？:：”)]}、)",
    'threads': '0',
    'vad_threshold': '0.45',
    'vad_min_speech_duration_ms': '250',
    'vad_max_speech_duration_s': '',
    'vad_min_silence_duration_ms': '3000',
    'vad_speech_pad_ms': '900',
    'vad_window_size_samples': '1536',
    'vad_dump': 'False',
    'vad_dump_aud': 'False',
    'vad_device': 'cuda',
    'hallucination_silence_threshold': '',
    'hallucination_silence_th_temp': '1.0',
    'clip_timestamps': '0',
    'max_new_tokens': '',
    'chunk_length': '',
    'postfix': 'False',
    'skip': 'False',
    'beep_off': 'False',
    'check_files': 'False',
    'alt_writer_off': 'False',
    'hallucinations_list_off': 'False',
    'v3_offsets_off': 'False',
    'prompt_reset_on_no_end': '2',
    'one_word': '0',
    'standard': 'False',
    'standard_asia': 'False',
    'max_comma': '250',
    'max_comma_cent': '100',
    'max_gap': '3.0',
    'max_line_width': '1000',
    'max_line_count': '1',
    'min_dist_to_end': '0',
    'ff_dump': 'False',
    'ff_track': '1',
    'ff_fc': 'False',
    'ff_mp3': 'False',
    'ff_sync': 'False',
    'ff_rnndn_sh': 'False',
    'ff_rnndn_xiph': 'False',
    'ff_fftdn': '0',
    'ff_tempo': '1.0',
    'ff_gate': 'False',
    'ff_speechnorm': 'False',
    'ff_loudnorm': 'False',
    'ff_silence_suppress': '0 3.0',
    'ff_lowhighpass': 'False',
    'diarize_device': 'cuda',
    'diarize_threads': '0',
    'speaker': 'SPEAKER',
})

if config.get_boolean('Settings', 'enable_logging', fallback=True):
    logging.basicConfig(filename='transcription.log', level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')


def enable_logging():
    return config.get_boolean('Settings', 'enable_logging', fallback=True)


def validate_file_extension(filename):
    valid_extensions = ('.wav', '.mp3', '.m4a', '.ogg', '.mp4',
                        '.mkv', '.avi', '.webm')
    return any(filename.lower().endswith(ext) for ext in valid_extensions)


def validate_numeric_input(value, min_value=None, max_value=None, allow_empty=True):
    if allow_empty and value.strip() == '':
        return True
    try:
        numeric_value = float(value)
        if min_value is not None and numeric_value < min_value:
            return False
        if max_value is not None and numeric_value > max_value:
            return False
        return True
    except ValueError:
        return False


def download_audio(url):
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)

    filename_template = os.path.join(output_dir, "%(id)s.%(ext)s")
    command = [
        "yt-dlp",
        "-f", "bestaudio",
        "--output", filename_template,
        url
    ]

    if enable_logging():
        logging.info(f"Executing yt-dlp command: {' '.join(command)}")

    result = subprocess.run(command, check=True, text=True, capture_output=True)
    if enable_logging():
        logging.info(f"yt-dlp stdout: {result.stdout}")
        logging.info(f"yt-dlp stderr: {result.stderr}")

    output_filename = None

    for line in result.stdout.splitlines():
        if "Destination:" in line:
            output_filename = line.split("Destination: ")[-1].strip()
            break

    if output_filename is None:
        for line in result.stdout.splitlines():
            if "[download]" in line and (".webm" in line or ".m4a" in line or ".mp3" in line):
                parts = line.split(']')
                if len(parts) > 1:
                    line_after_bracket = parts[1].strip()
                    possible_file = line_after_bracket.split(' ')[0].strip()
                    full_path = os.path.join(os.getcwd(), possible_file)
                    if os.path.exists(full_path):
                        output_filename = full_path
                        break
                    elif os.path.exists(possible_file):
                        output_filename = possible_file
                        break

    if output_filename is None:
        files_in_downloads = os.listdir(output_dir)
        if files_in_downloads:
            newest_file = max([os.path.join(output_dir, f) for f in files_in_downloads], key=os.path.getctime)
            if os.path.isfile(newest_file):
                output_filename = newest_file

    if output_filename is None or not os.path.isfile(output_filename):
        raise Exception("Failed to locate the downloaded file.")

    if enable_logging():
        logging.info(f"Downloaded file location: {output_filename}")

    return output_filename


class TranscriptionWorker(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, file_list, widget_dict):
        super().__init__()
        self.file_list = file_list
        self.widget_dict = widget_dict

    def run(self):
        try:
            self.run_transcription()
        except Exception as e:
            self.error_occurred.emit(f"An unexpected error occurred: {e}")
            if enable_logging():
                logging.error(f"An unexpected error occurred during transcription: {e}")

    def build_command_args(self, filename):
        language = self.widget_dict['language'].currentText()
        if language == "Auto Detect":
            language = None
        model = self.widget_dict['model'].currentText()
        task = self.widget_dict['task'].currentText()

        selected_formats = []
        for fmt, cb in self.widget_dict['output_formats'].items():
            if cb.isChecked():
                selected_formats.append(fmt)
        if not selected_formats:
            selected_formats = ["txt"]

        output_dir = self.widget_dict['output_dir'].text() or "output"
        exe_path = config.get('Settings', 'exe_path', fallback=DEFAULT_VALUES['exe_path']) or "faster-whisper-xxl.exe"

        ff_mdx_kim2 = self.widget_dict['ff_mdx_kim2'].isChecked()

        vad_filter_val = "True" if self.widget_dict['vad_filter'].isChecked() else "False"
        vad_method = self.widget_dict['vad_method'].currentText() if self.widget_dict['vad_filter'].isChecked() else ""

        word_timestamps_val = "True" if self.widget_dict['word_timestamps'].isChecked() else "False"
        sentence = self.widget_dict['sentence'].isChecked()
        diarize = self.widget_dict['diarize'].isChecked()
        diarize_method = self.widget_dict['diarize_method'].currentText().strip()
        num_speakers = self.widget_dict['num_speakers'].text().strip()
        min_speakers = self.widget_dict['min_speakers'].text().strip()
        max_speakers = self.widget_dict['max_speakers'].text().strip()
        diarize_dump = self.widget_dict['diarize_dump'].text().strip()
        hotwords = self.widget_dict['hotwords'].text().strip()
        rehot = self.widget_dict['rehot'].isChecked()

        ignore_dupe_prompt_val = self.widget_dict['ignore_dupe_prompt'].text().strip()
        if ignore_dupe_prompt_val == '':
            ignore_dupe_prompt_val = '2'
        try:
            int(ignore_dupe_prompt_val)
        except ValueError:
            ignore_dupe_prompt_val = '2'

        multilingual_val = "True" if self.widget_dict['multilingual'].isChecked() else "False"
        batch_size = self.widget_dict['batch_size'].text().strip()
        batched = self.widget_dict['batched'].isChecked()
        unmerged = self.widget_dict['unmerged'].isChecked()

        # Additional arguments from UI
        language_detection_threshold = self.widget_dict['language_detection_threshold'].text()
        language_detection_segments = self.widget_dict['language_detection_segments'].text()
        patience = self.widget_dict['patience'].text()
        length_penalty = self.widget_dict['length_penalty'].text()
        repetition_penalty = self.widget_dict['repetition_penalty'].text()
        no_repeat_ngram_size = self.widget_dict['no_repeat_ngram_size'].text()
        suppress_blank_val = "True" if self.widget_dict['suppress_blank'].isChecked() else "False"
        suppress_tokens = self.widget_dict['suppress_tokens'].text()
        initial_prompt = self.widget_dict['initial_prompt'].text()
        prefix = self.widget_dict['prefix'].text()
        condition_on_previous_text_val = "True" if self.widget_dict['condition_on_previous_text'].isChecked() else "False"
        prompt_reset_on_temperature = self.widget_dict['prompt_reset_on_temperature'].text()
        without_timestamps_val = "True" if self.widget_dict['without_timestamps'].isChecked() else "False"
        max_initial_timestamp = self.widget_dict['max_initial_timestamp'].text()
        temperature_increment_on_fallback = self.widget_dict['temperature_increment_on_fallback'].text()
        compression_ratio_threshold = self.widget_dict['compression_ratio_threshold'].text()
        logprob_threshold = self.widget_dict['logprob_threshold'].text()
        no_speech_threshold = self.widget_dict['no_speech_threshold'].text()
        highlight_words_val = "True" if self.widget_dict['highlight_words'].isChecked() else "False"
        prepend_punctuations = self.widget_dict['prepend_punctuations'].text()
        append_punctuations = self.widget_dict['append_punctuations'].text()
        threads = self.widget_dict['threads'].text()
        temperature = self.widget_dict['temperature'].text()
        beam_size = self.widget_dict['beam_size'].text()
        best_of = self.widget_dict['best_of'].text()
        mdx_chunk = self.widget_dict['mdx_chunk'].text()
        mdx_device = self.widget_dict['mdx_device'].text()
        compute_type = self.widget_dict['compute_type'].currentText()

        vad_threshold = self.widget_dict['vad_threshold'].text()
        vad_min_speech_duration_ms = self.widget_dict['vad_min_speech_duration_ms'].text()
        vad_max_speech_duration_s = self.widget_dict['vad_max_speech_duration_s'].text()
        vad_min_silence_duration_ms = self.widget_dict['vad_min_silence_duration_ms'].text()
        vad_speech_pad_ms = self.widget_dict['vad_speech_pad_ms'].text()
        vad_window_size_samples = self.widget_dict['vad_window_size_samples'].text()
        vad_dump = "True" if self.widget_dict['vad_dump'].isChecked() else "False"
        vad_dump_aud = "True" if self.widget_dict['vad_dump_aud'].isChecked() else "False"
        vad_device = self.widget_dict['vad_device'].text()
        hallucination_silence_threshold = self.widget_dict['hallucination_silence_threshold'].text()
        hallucination_silence_th_temp = self.widget_dict['hallucination_silence_th_temp'].currentText()
        clip_timestamps = self.widget_dict['clip_timestamps'].text()
        max_new_tokens = self.widget_dict['max_new_tokens'].text()
        chunk_length = self.widget_dict['chunk_length'].text()

        postfix = self.widget_dict['postfix'].isChecked()
        skip = self.widget_dict['skip'].isChecked()
        beep_off = self.widget_dict['beep_off'].isChecked()
        check_files = self.widget_dict['check_files'].isChecked()
        alt_writer_off = self.widget_dict['alt_writer_off'].isChecked()
        hallucinations_list_off = self.widget_dict['hallucinations_list_off'].isChecked()
        v3_offsets_off = self.widget_dict['v3_offsets_off'].isChecked()
        prompt_reset_on_no_end = self.widget_dict['prompt_reset_on_no_end'].currentText()
        rehot_val = rehot
        one_word = self.widget_dict['one_word'].currentText()
        sentence_val = sentence
        standard = self.widget_dict['standard'].isChecked()
        standard_asia = self.widget_dict['standard_asia'].isChecked()
        max_comma = self.widget_dict['max_comma'].text()
        max_comma_cent = self.widget_dict['max_comma_cent'].currentText()
        max_gap = self.widget_dict['max_gap'].text()
        max_line_width = self.widget_dict['max_line_width'].text()
        max_line_count = self.widget_dict['max_line_count'].text()
        min_dist_to_end = self.widget_dict['min_dist_to_end'].currentText()

        ff_dump = self.widget_dict['ff_dump'].isChecked()
        ff_track = self.widget_dict['ff_track'].currentText()
        ff_fc = self.widget_dict['ff_fc'].isChecked()
        ff_mp3 = self.widget_dict['ff_mp3'].isChecked()
        ff_sync = self.widget_dict['ff_sync'].isChecked()
        ff_rnndn_sh = self.widget_dict['ff_rnndn_sh'].isChecked()
        ff_rnndn_xiph = self.widget_dict['ff_rnndn_xiph'].isChecked()
        ff_fftdn = self.widget_dict['ff_fftdn'].text()
        ff_tempo = self.widget_dict['ff_tempo'].text()
        ff_gate = self.widget_dict['ff_gate'].isChecked()
        ff_speechnorm = self.widget_dict['ff_speechnorm'].isChecked()
        ff_loudnorm = self.widget_dict['ff_loudnorm'].isChecked()
        ff_silence_suppress = self.widget_dict['ff_silence_suppress'].text()
        ff_lowhighpass = self.widget_dict['ff_lowhighpass'].isChecked()

        diarize_device = self.widget_dict['diarize_device'].text()
        diarize_threads = self.widget_dict['diarize_threads'].text()
        speaker = self.widget_dict['speaker'].text()

        command = [exe_path, filename, "--model", model]
        if task != "transcribe":
            command.extend(["--task", task])
        command.extend(["--output_dir", output_dir])

        for fmt in selected_formats:
            command.extend(["--output_format", fmt])
        command.extend(["--compute_type", compute_type])

        if language:
            command.extend(["--language", language])
        if ff_mdx_kim2:
            command.extend(["--ff_mdx_kim2", "--mdx_chunk", mdx_chunk, "--mdx_device", mdx_device])

        command.extend(["--vad_filter", vad_filter_val])
        if self.widget_dict['vad_filter'].isChecked() and vad_method:
            command.extend(["--vad_method", vad_method])

        command.extend(["--word_timestamps", word_timestamps_val])
        if sentence_val:
            command.append("--sentence")

        command.extend(["--temperature", temperature])
        command.extend(["--beam_size", beam_size])
        command.extend(["--best_of", best_of])

        # Additional arguments
        if diarize:
            command.extend(["--diarize", diarize_method])
            if num_speakers:
                command.extend(["--num_speakers", num_speakers])
            if min_speakers:
                command.extend(["--min_speakers", min_speakers])
            if max_speakers:
                command.extend(["--max_speakers", max_speakers])
            if diarize_dump.strip():
                command.append("--diarize_dump")

        if hotwords.strip():
            command.extend(["--hotwords", hotwords])
        if rehot_val:
            command.append("--rehot")

        command.extend(["--ignore_dupe_prompt", ignore_dupe_prompt_val])
        command.extend(["--multilingual", multilingual_val])

        if batch_size:
            command.extend(["--batch_size", batch_size])
        if batched:
            command.append("--batched")
        if unmerged:
            command.append("--unmerged")

        # Additional decoding/prompting parameters
        command.extend(["--language_detection_threshold", language_detection_threshold])
        command.extend(["--language_detection_segments", language_detection_segments])
        command.extend(["--patience", patience])
        command.extend(["--length_penalty", length_penalty])
        command.extend(["--repetition_penalty", repetition_penalty])
        command.extend(["--no_repeat_ngram_size", no_repeat_ngram_size])
        command.extend(["--suppress_blank", suppress_blank_val])
        if suppress_tokens.strip():
            command.extend(["--suppress_tokens", suppress_tokens])
        if initial_prompt.strip():
            command.extend(["--initial_prompt", initial_prompt])
        if prefix.strip():
            command.extend(["--prefix", prefix])
        command.extend(["--condition_on_previous_text", condition_on_previous_text_val])
        command.extend(["--prompt_reset_on_temperature", prompt_reset_on_temperature])
        if without_timestamps_val == "True":
            command.append("--without_timestamps")
        command.extend(["--max_initial_timestamp", max_initial_timestamp])
        if temperature_increment_on_fallback.strip() and temperature_increment_on_fallback.lower() != 'none':
            command.extend(["--temperature_increment_on_fallback", temperature_increment_on_fallback])
        command.extend(["--compression_ratio_threshold", compression_ratio_threshold])
        command.extend(["--logprob_threshold", logprob_threshold])
        command.extend(["--no_speech_threshold", no_speech_threshold])
        if highlight_words_val == "True":
            command.append("--highlight_words")
        if prepend_punctuations.strip():
            command.extend(["--prepend_punctuations", prepend_punctuations])
        if append_punctuations.strip():
            command.extend(["--append_punctuations", append_punctuations])
        if threads.strip():
            command.extend(["--threads", threads])

        # VAD related arguments
        command.extend(["--vad_threshold", vad_threshold])
        if vad_min_speech_duration_ms.strip():
            command.extend(["--vad_min_speech_duration_ms", vad_min_speech_duration_ms])
        if vad_max_speech_duration_s.strip():
            command.extend(["--vad_max_speech_duration_s", vad_max_speech_duration_s])
        if vad_min_silence_duration_ms.strip():
            command.extend(["--vad_min_silence_duration_ms", vad_min_silence_duration_ms])
        if vad_speech_pad_ms.strip():
            command.extend(["--vad_speech_pad_ms", vad_speech_pad_ms])
        if vad_window_size_samples.strip():
            command.extend(["--vad_window_size_samples", vad_window_size_samples])
        if vad_dump == "True":
            command.append("--vad_dump")
        if vad_dump_aud == "True":
            command.append("--vad_dump_aud")
        if vad_device.strip():
            command.extend(["--vad_device", vad_device])

        # Hallucination silence
        if hallucination_silence_threshold.strip():
            command.extend(["--hallucination_silence_threshold", hallucination_silence_threshold])
        if hallucination_silence_th_temp != "1.0":
            command.extend(["--hallucination_silence_th_temp", hallucination_silence_th_temp])

        # Clip timestamps
        if clip_timestamps.strip() != "0":
            command.extend(["--clip_timestamps", clip_timestamps])

        # max_new_tokens, chunk_length
        if max_new_tokens.strip():
            command.extend(["--max_new_tokens", max_new_tokens])
        if chunk_length.strip():
            command.extend(["--chunk_length", chunk_length])

        # Post-processing options
        if postfix:
            command.append("--postfix")
        if skip:
            command.append("--skip")
        if beep_off:
            command.append("--beep_off")
        if check_files:
            command.append("--check_files")
        if alt_writer_off:
            command.append("--alt_writer_off")
        if hallucinations_list_off:
            command.append("--hallucinations_list_off")
        if v3_offsets_off:
            command.append("--v3_offsets_off")
        if prompt_reset_on_no_end != "2":
            command.extend(["--prompt_reset_on_no_end", prompt_reset_on_no_end])
        if rehot_val:
            command.append("--rehot")
        if one_word != "0":
            command.extend(["--one_word", one_word])
        if standard:
            command.append("--standard")
        if standard_asia:
            command.append("--standard_asia")
        if max_comma.strip() != "250":
            command.extend(["--max_comma", max_comma])
        if max_comma_cent != "100":
            command.extend(["--max_comma_cent", max_comma_cent])
        if max_gap.strip() != "3.0":
            command.extend(["--max_gap", max_gap])
        if max_line_width.strip() != "1000":
            command.extend(["--max_line_width", max_line_width])
        if max_line_count.strip() != "1":
            command.extend(["--max_line_count", max_line_count])
        if min_dist_to_end != "0":
            command.extend(["--min_dist_to_end", min_dist_to_end])

        # Audio filters (ff_...)
        if ff_dump:
            command.append("--ff_dump")
        if ff_track != "1":
            command.extend(["--ff_track", ff_track])
        if ff_fc:
            command.append("--ff_fc")
        if ff_mp3:
            command.append("--ff_mp3")
        if ff_sync:
            command.append("--ff_sync")
        if ff_rnndn_sh:
            command.append("--ff_rnndn_sh")
        if ff_rnndn_xiph:
            command.append("--ff_rnndn_xiph")
        if ff_fftdn != "0":
            command.extend(["--ff_fftdn", ff_fftdn])
        if ff_tempo != "1.0":
            command.extend(["--ff_tempo", ff_tempo])
        if ff_gate:
            command.append("--ff_gate")
        if ff_speechnorm:
            command.append("--ff_speechnorm")
        if ff_loudnorm:
            command.append("--ff_loudnorm")
        if ff_silence_suppress.strip() != "0 3.0":
            # expected "noise duration"
            ss_parts = ff_silence_suppress.split()
            if len(ss_parts) == 2:
                command.extend(["--ff_silence_suppress", ss_parts[0], ss_parts[1]])
        if ff_lowhighpass:
            command.append("--ff_lowhighpass")

        # Diarization device, threads, speaker
        if diarize_device.strip():
            command.extend(["--diarize_device", diarize_device])
        if diarize_threads.strip() != "0":
            command.extend(["--diarize_threads", diarize_threads])
        if speaker.strip() != "SPEAKER":
            command.extend(["--speaker", speaker])

        return command

    def run_transcription(self):
        if not self.file_list:
            self.error_occurred.emit("Please select at least one file or provide a link.")
            return

        total_files = len(self.file_list)
        self.progress_updated.emit(0, f"Progress: 0/{total_files}")

        for index, file_path in enumerate(self.file_list, start=1):
            if file_path.startswith(("http://", "https://")):
                try:
                    filename = download_audio(file_path)
                except Exception as e:
                    self.error_occurred.emit(f"Failed to download from {file_path}: {e}")
                    if enable_logging():
                        logging.error(f"Failed to download from {file_path}: {e}")
                    continue
            else:
                filename = file_path

            command = self.build_command_args(filename)

            if enable_logging():
                logging.info("Command:")
                logging.info(" ".join(command))

            try:
                subprocess.run(command, shell=False, check=True)
                progress = int((index / total_files) * 100)
                self.progress_updated.emit(progress, f"Progress: {index}/{total_files}")
                if enable_logging():
                    logging.info(f"Transcription complete for {filename}.")
            except subprocess.CalledProcessError as e:
                self.error_occurred.emit(f"An error occurred during transcription of {filename}: {e}")
                if enable_logging():
                    logging.error(f"An error occurred during transcription of {filename}: {e}")

        self.finished.emit()


class Expander(QWidget):
    def __init__(self, label, target):
        super().__init__()
        self.label = label
        self.target = target
        self.collapsed = True
        self.init_ui()
        self.target.setVisible(False)
        self.update_header_label()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel()
        self.header.setStyleSheet("QLabel {font-weight: bold;}")
        self.header.mouseReleaseEvent = self.expand_collapse
        self.layout.addWidget(self.header)
        self.layout.addWidget(self.target)
        self.setLayout(self.layout)
        self.update_header_label()

    def expand_collapse(self, event):
        self.collapsed = not self.collapsed
        self.target.setVisible(not self.collapsed)
        self.update_header_label()

    def update_header_label(self):
        if self.collapsed:
            self.header.setText(self.label + " ▼")
        else:
            self.header.setText(self.label + " ▲")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Whisper Transcription App")
        self.resize(800, 1200)
        pixmap = QPixmap()
        pixmap.loadFromData(base64.b64decode(base64_icon))
        self.setWindowIcon(QIcon(pixmap))

        self.widget_dict = {}
        self.create_widgets()
        self.create_layout()
        self.load_settings()
        self.setAcceptDrops(True)
        self.load_window_geometry()

    def closeEvent(self, event):
        self.save_window_geometry()
        event.accept()

    def load_window_geometry(self):
        geometry = config.get('Settings', 'window_geometry', fallback='')
        if geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode('utf-8')))

    def save_window_geometry(self):
        config.config['Settings']['window_geometry'] = self.saveGeometry().toBase64().data().decode('utf-8')
        config.save_config()

    def save_settings(self):
        config.save_config(self.widget_dict)
        self.save_window_geometry()

    def create_widgets(self):
        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_files)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_files)
        self.file_entry = QLineEdit()
        self.file_entry.setPlaceholderText("Enter file path or URL")
        self.add_file_button = QPushButton("Add")
        self.add_file_button.clicked.connect(self.add_file_from_entry)

        self.widget_dict['language'] = QComboBox()
        self.widget_dict['language'].addItems(SUPPORTED_LANGUAGES)
        self.widget_dict['model'] = QComboBox()
        self.widget_dict['model'].addItems(WHISPER_MODELS)
        self.widget_dict['task'] = QComboBox()
        self.widget_dict['task'].addItems(TASK_OPTIONS)

        self.widget_dict['output_formats'] = {}
        for fmt in OUTPUT_FORMAT_OPTIONS:
            cb = QCheckBox(fmt)
            self.widget_dict['output_formats'][fmt] = cb

        self.widget_dict['output_dir'] = QLineEdit()
        self.browse_output_dir_button = QPushButton("Browse")
        self.browse_output_dir_button.clicked.connect(self.browse_output_dir)

        self.widget_dict['ff_mdx_kim2'] = QCheckBox("Enable FF MDX Kim2")
        self.widget_dict['vad_filter'] = QCheckBox("Enable VAD Filter")
        self.widget_dict['vad_method'] = QComboBox()
        self.widget_dict['vad_method'].addItems(VAD_METHOD_OPTIONS)
        self.widget_dict['word_timestamps'] = QCheckBox("Enable Word Timestamps")
        self.widget_dict['sentence'] = QCheckBox("Split into sentences")
        self.widget_dict['compute_type'] = QComboBox()
        self.widget_dict['compute_type'].addItems(COMPUTE_TYPE_OPTIONS)
        self.widget_dict['temperature'] = QLineEdit()
        self.widget_dict['beam_size'] = QLineEdit()
        self.widget_dict['best_of'] = QLineEdit()
        self.widget_dict['mdx_chunk'] = QLineEdit()
        self.widget_dict['mdx_device'] = QLineEdit()
        self.widget_dict['enable_logging'] = QCheckBox("Enable Logging")

        self.widget_dict['diarize'] = QCheckBox("Enable Diarization")
        self.widget_dict['diarize_method'] = QComboBox()
        self.widget_dict['diarize_method'].addItems(DIARIZE_METHOD_OPTIONS)
        self.widget_dict['num_speakers'] = QLineEdit()
        self.widget_dict['min_speakers'] = QLineEdit()
        self.widget_dict['max_speakers'] = QLineEdit()
        self.widget_dict['diarize_dump'] = QLineEdit()
        self.widget_dict['hotwords'] = QLineEdit()
        self.widget_dict['rehot'] = QCheckBox("Re-Hotwords")

        self.widget_dict['ignore_dupe_prompt'] = QLineEdit()
        self.widget_dict['ignore_dupe_prompt'].setPlaceholderText("Integer (default 2)")

        self.widget_dict['multilingual'] = QCheckBox("Multilingual")
        self.widget_dict['batch_size'] = QLineEdit()
        self.widget_dict['batched'] = QCheckBox("Batched")
        self.widget_dict['unmerged'] = QCheckBox("Unmerged")

        self.widget_dict['exe_path'] = QLineEdit()
        self.widget_dict['exe_path'].setPlaceholderText("Path to whisper-standalone exe (optional)")

        # Additional advanced arguments
        # We'll create several groups for them

        # Decoding Parameters
        self.widget_dict['language_detection_threshold'] = QLineEdit()
        self.widget_dict['language_detection_segments'] = QLineEdit()
        self.widget_dict['patience'] = QLineEdit()
        self.widget_dict['length_penalty'] = QLineEdit()
        self.widget_dict['repetition_penalty'] = QLineEdit()
        self.widget_dict['no_repeat_ngram_size'] = QLineEdit()
        self.widget_dict['suppress_blank'] = QCheckBox("Suppress Blank")
        self.widget_dict['suppress_tokens'] = QLineEdit()
        self.widget_dict['initial_prompt'] = QLineEdit()
        self.widget_dict['prefix'] = QLineEdit()
        self.widget_dict['condition_on_previous_text'] = QCheckBox("Condition on Previous Text")
        self.widget_dict['prompt_reset_on_temperature'] = QLineEdit()
        self.widget_dict['without_timestamps'] = QCheckBox("Without Timestamps")
        self.widget_dict['max_initial_timestamp'] = QLineEdit()
        self.widget_dict['temperature_increment_on_fallback'] = QLineEdit()
        self.widget_dict['compression_ratio_threshold'] = QLineEdit()
        self.widget_dict['logprob_threshold'] = QLineEdit()
        self.widget_dict['no_speech_threshold'] = QLineEdit()

        self.widget_dict['highlight_words'] = QCheckBox("Highlight Words")
        self.widget_dict['prepend_punctuations'] = QLineEdit()
        self.widget_dict['append_punctuations'] = QLineEdit()
        self.widget_dict['threads'] = QLineEdit()

        # VAD Settings
        self.widget_dict['vad_threshold'] = QLineEdit()
        self.widget_dict['vad_min_speech_duration_ms'] = QLineEdit()
        self.widget_dict['vad_max_speech_duration_s'] = QLineEdit()
        self.widget_dict['vad_min_silence_duration_ms'] = QLineEdit()
        self.widget_dict['vad_speech_pad_ms'] = QLineEdit()
        self.widget_dict['vad_window_size_samples'] = QLineEdit()
        self.widget_dict['vad_dump'] = QCheckBox("VAD Dump")
        self.widget_dict['vad_dump_aud'] = QCheckBox("VAD Dump Aud")
        self.widget_dict['vad_device'] = QLineEdit()

        # Hallucination & Clip
        self.widget_dict['hallucination_silence_threshold'] = QLineEdit()
        self.widget_dict['hallucination_silence_th_temp'] = QComboBox()
        self.widget_dict['hallucination_silence_th_temp'].addItems(["0.0","0.2","0.5","0.8","1.0"])
        self.widget_dict['clip_timestamps'] = QLineEdit()

        # Additional segment & batch parameters
        self.widget_dict['max_new_tokens'] = QLineEdit()
        self.widget_dict['chunk_length'] = QLineEdit()

        # Post-processing
        self.widget_dict['postfix'] = QCheckBox("Postfix")
        self.widget_dict['skip'] = QCheckBox("Skip")
        self.widget_dict['beep_off'] = QCheckBox("Beep Off")
        self.widget_dict['check_files'] = QCheckBox("Check Files")
        self.widget_dict['alt_writer_off'] = QCheckBox("Alt Writer Off")
        self.widget_dict['hallucinations_list_off'] = QCheckBox("Hallucinations List Off")
        self.widget_dict['v3_offsets_off'] = QCheckBox("V3 Offsets Off")
        self.widget_dict['prompt_reset_on_no_end'] = QComboBox()
        self.widget_dict['prompt_reset_on_no_end'].addItems(["0","1","2"])
        self.widget_dict['one_word'] = QComboBox()
        self.widget_dict['one_word'].addItems(["0","1","2"])
        self.widget_dict['standard'] = QCheckBox("Standard")
        self.widget_dict['standard_asia'] = QCheckBox("Standard Asia")
        self.widget_dict['max_comma'] = QLineEdit()
        self.widget_dict['max_comma_cent'] = QComboBox()
        self.widget_dict['max_comma_cent'].addItems(["20","30","40","50","60","70","80","90","100"])
        self.widget_dict['max_gap'] = QLineEdit()
        self.widget_dict['max_line_width'] = QLineEdit()
        self.widget_dict['max_line_count'] = QLineEdit()
        self.widget_dict['min_dist_to_end'] = QComboBox()
        self.widget_dict['min_dist_to_end'].addItems(["0","4","5","6","7","8","9","10","11","12"])

        # Audio Filters
        self.widget_dict['ff_dump'] = QCheckBox("FF Dump")
        self.widget_dict['ff_track'] = QComboBox()
        self.widget_dict['ff_track'].addItems(["1","2","3","4","5","6"])
        self.widget_dict['ff_fc'] = QCheckBox("FF Front-Center")
        self.widget_dict['ff_mp3'] = QCheckBox("FF MP3")
        self.widget_dict['ff_sync'] = QCheckBox("FF Sync")
        self.widget_dict['ff_rnndn_sh'] = QCheckBox("FF RNNDN SH")
        self.widget_dict['ff_rnndn_xiph'] = QCheckBox("FF RNNDN Xiph")
        self.widget_dict['ff_fftdn'] = QLineEdit()
        self.widget_dict['ff_tempo'] = QLineEdit()
        self.widget_dict['ff_gate'] = QCheckBox("FF Gate")
        self.widget_dict['ff_speechnorm'] = QCheckBox("FF SpeechNorm")
        self.widget_dict['ff_loudnorm'] = QCheckBox("FF LoudNorm")
        self.widget_dict['ff_silence_suppress'] = QLineEdit()
        self.widget_dict['ff_lowhighpass'] = QCheckBox("FF LowHighPass")

        # Diarization extras
        self.widget_dict['diarize_device'] = QLineEdit()
        self.widget_dict['diarize_threads'] = QLineEdit()
        self.widget_dict['speaker'] = QLineEdit()

        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("Progress: 0/0")
        self.transcribe_button = QPushButton("Start")
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)

    def create_layout(self):
        main_layout = QVBoxLayout()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)

        file_selection_layout = QGridLayout()
        file_selection_layout.addWidget(QLabel("Audio/Video Files:"), 0, 0, 1, 2)
        file_selection_layout.addWidget(self.file_list_widget, 1, 0, 1, 2)
        file_selection_layout.addWidget(self.file_entry, 2, 0)
        file_selection_layout.addWidget(self.add_file_button, 2, 1)
        file_selection_layout.addWidget(self.browse_button, 3, 0)
        file_selection_layout.addWidget(self.clear_button, 3, 1)
        container_layout.addLayout(file_selection_layout)

        options_group_box = QGroupBox("Basic Options")
        options_layout = QFormLayout()
        options_layout.addRow("Language:", self.widget_dict['language'])
        options_layout.addRow("Model:", self.widget_dict['model'])
        options_layout.addRow("Task:", self.widget_dict['task'])

        output_format_layout = QHBoxLayout()
        for fmt, cb in self.widget_dict['output_formats'].items():
            output_format_layout.addWidget(cb)
        fmt_box = QGroupBox("Output Formats")
        fmt_box.setLayout(output_format_layout)
        options_layout.addRow(fmt_box)

        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self.widget_dict['output_dir'])
        output_dir_layout.addWidget(self.browse_output_dir_button)
        options_layout.addRow("Output Directory:", output_dir_layout)
        options_group_box.setLayout(options_layout)
        container_layout.addWidget(options_group_box)

        advanced_widget = QWidget()
        advanced_form = QFormLayout(advanced_widget)
        advanced_form.addRow(self.widget_dict['ff_mdx_kim2'])
        adv_vad_layout = QHBoxLayout()
        adv_vad_layout.addWidget(self.widget_dict['vad_filter'])
        adv_vad_layout.addWidget(QLabel("Method:"))
        adv_vad_layout.addWidget(self.widget_dict['vad_method'])
        advanced_form.addRow("VAD:", adv_vad_layout)

        advanced_form.addRow(self.widget_dict['word_timestamps'])
        advanced_form.addRow(self.widget_dict['sentence'])
        advanced_form.addRow("Compute Type:", self.widget_dict['compute_type'])
        advanced_form.addRow("Temperature:", self.widget_dict['temperature'])
        advanced_form.addRow("Beam Size:", self.widget_dict['beam_size'])
        advanced_form.addRow("Best Of:", self.widget_dict['best_of'])
        advanced_form.addRow("MDX Chunk (seconds):", self.widget_dict['mdx_chunk'])
        advanced_form.addRow("MDX Device:", self.widget_dict['mdx_device'])
        advanced_form.addRow(self.widget_dict['enable_logging'])
        advanced_form.addRow("Executable Path:", self.widget_dict['exe_path'])

        # Diarization box
        diarize_box = QGroupBox("Diarization")
        diarize_layout = QFormLayout(diarize_box)
        diarize_layout.addRow(self.widget_dict['diarize'])
        diarize_layout.addRow("Diarize Method:", self.widget_dict['diarize_method'])
        diarize_layout.addRow("Num Speakers:", self.widget_dict['num_speakers'])
        diarize_layout.addRow("Min Speakers:", self.widget_dict['min_speakers'])
        diarize_layout.addRow("Max Speakers:", self.widget_dict['max_speakers'])
        diarize_layout.addRow("Diarize Dump:", self.widget_dict['diarize_dump'])
        diarize_layout.addRow("Hotwords:", self.widget_dict['hotwords'])
        diarize_layout.addRow(self.widget_dict['rehot'])
        diarize_layout.addRow("Ignore Dupe Prompt (int):", self.widget_dict['ignore_dupe_prompt'])
        diarize_layout.addRow(self.widget_dict['multilingual'])
        diarize_layout.addRow("Batch Size:", self.widget_dict['batch_size'])
        diarize_layout.addRow(self.widget_dict['batched'])
        diarize_layout.addRow(self.widget_dict['unmerged'])
        diarize_layout.addRow("Diarize Device:", self.widget_dict['diarize_device'])
        diarize_layout.addRow("Diarize Threads:", self.widget_dict['diarize_threads'])
        diarize_layout.addRow("Speaker:", self.widget_dict['speaker'])

        # Decoding parameters
        decoding_box = QGroupBox("Decoding Parameters")
        decoding_layout = QFormLayout(decoding_box)
        decoding_layout.addRow("Language Detection Threshold:", self.widget_dict['language_detection_threshold'])
        decoding_layout.addRow("Language Detection Segments:", self.widget_dict['language_detection_segments'])
        decoding_layout.addRow("Patience:", self.widget_dict['patience'])
        decoding_layout.addRow("Length Penalty:", self.widget_dict['length_penalty'])
        decoding_layout.addRow("Repetition Penalty:", self.widget_dict['repetition_penalty'])
        decoding_layout.addRow("No Repeat Ngram Size:", self.widget_dict['no_repeat_ngram_size'])
        decoding_layout.addRow(self.widget_dict['suppress_blank'])
        decoding_layout.addRow("Suppress Tokens:", self.widget_dict['suppress_tokens'])
        decoding_layout.addRow("Initial Prompt:", self.widget_dict['initial_prompt'])
        decoding_layout.addRow("Prefix:", self.widget_dict['prefix'])
        decoding_layout.addRow(self.widget_dict['condition_on_previous_text'])
        decoding_layout.addRow("Prompt Reset on Temperature:", self.widget_dict['prompt_reset_on_temperature'])
        decoding_layout.addRow(self.widget_dict['without_timestamps'])
        decoding_layout.addRow("Max Initial Timestamp:", self.widget_dict['max_initial_timestamp'])
        decoding_layout.addRow("Temperature Increment on Fallback:", self.widget_dict['temperature_increment_on_fallback'])
        decoding_layout.addRow("Compression Ratio Threshold:", self.widget_dict['compression_ratio_threshold'])
        decoding_layout.addRow("Logprob Threshold:", self.widget_dict['logprob_threshold'])
        decoding_layout.addRow("No Speech Threshold:", self.widget_dict['no_speech_threshold'])
        decoding_layout.addRow(self.widget_dict['highlight_words'])
        decoding_layout.addRow("Prepend Punctuations:", self.widget_dict['prepend_punctuations'])
        decoding_layout.addRow("Append Punctuations:", self.widget_dict['append_punctuations'])
        decoding_layout.addRow("Threads:", self.widget_dict['threads'])

        # VAD Settings box
        vad_box = QGroupBox("VAD Settings")
        vad_layout = QFormLayout(vad_box)
        vad_layout.addRow("VAD Threshold:", self.widget_dict['vad_threshold'])
        vad_layout.addRow("VAD Min Speech Duration (ms):", self.widget_dict['vad_min_speech_duration_ms'])
        vad_layout.addRow("VAD Max Speech Duration (s):", self.widget_dict['vad_max_speech_duration_s'])
        vad_layout.addRow("VAD Min Silence Duration (ms):", self.widget_dict['vad_min_silence_duration_ms'])
        vad_layout.addRow("VAD Speech Pad (ms):", self.widget_dict['vad_speech_pad_ms'])
        vad_layout.addRow("VAD Window Size (samples):", self.widget_dict['vad_window_size_samples'])
        vad_layout.addRow(self.widget_dict['vad_dump'])
        vad_layout.addRow(self.widget_dict['vad_dump_aud'])
        vad_layout.addRow("VAD Device:", self.widget_dict['vad_device'])

        # Hallucination & Clip
        hallucination_box = QGroupBox("Hallucination & Clipping")
        hallucination_layout = QFormLayout(hallucination_box)
        hallucination_layout.addRow("Hallucination Silence Threshold:", self.widget_dict['hallucination_silence_threshold'])
        hallucination_layout.addRow("Hallucination Silence TH Temp:", self.widget_dict['hallucination_silence_th_temp'])
        hallucination_layout.addRow("Clip Timestamps:", self.widget_dict['clip_timestamps'])

        # Additional segments/batch
        extra_box = QGroupBox("Extra Decoding Options")
        extra_layout = QFormLayout(extra_box)
        extra_layout.addRow("Max New Tokens:", self.widget_dict['max_new_tokens'])
        extra_layout.addRow("Chunk Length:", self.widget_dict['chunk_length'])

        # Post-processing
        post_box = QGroupBox("Post-processing")
        post_layout = QFormLayout(post_box)
        post_layout.addRow(self.widget_dict['postfix'])
        post_layout.addRow(self.widget_dict['skip'])
        post_layout.addRow(self.widget_dict['beep_off'])
        post_layout.addRow(self.widget_dict['check_files'])
        post_layout.addRow(self.widget_dict['alt_writer_off'])
        post_layout.addRow(self.widget_dict['hallucinations_list_off'])
        post_layout.addRow(self.widget_dict['v3_offsets_off'])
        post_layout.addRow("Prompt Reset on No End:", self.widget_dict['prompt_reset_on_no_end'])
        post_layout.addRow("One Word:", self.widget_dict['one_word'])
        post_layout.addRow(self.widget_dict['standard'])
        post_layout.addRow(self.widget_dict['standard_asia'])
        post_layout.addRow("Max Comma:", self.widget_dict['max_comma'])
        post_layout.addRow("Max Comma Cent:", self.widget_dict['max_comma_cent'])
        post_layout.addRow("Max Gap:", self.widget_dict['max_gap'])
        post_layout.addRow("Max Line Width:", self.widget_dict['max_line_width'])
        post_layout.addRow("Max Line Count:", self.widget_dict['max_line_count'])
        post_layout.addRow("Min Dist to End:", self.widget_dict['min_dist_to_end'])

        # Audio Filters
        filters_box = QGroupBox("Audio Filters")
        filters_layout = QFormLayout(filters_box)
        filters_layout.addRow(self.widget_dict['ff_dump'])
        filters_layout.addRow("FF Track:", self.widget_dict['ff_track'])
        filters_layout.addRow(self.widget_dict['ff_fc'])
        filters_layout.addRow(self.widget_dict['ff_mp3'])
        filters_layout.addRow(self.widget_dict['ff_sync'])
        filters_layout.addRow(self.widget_dict['ff_rnndn_sh'])
        filters_layout.addRow(self.widget_dict['ff_rnndn_xiph'])
        filters_layout.addRow("FF FFTDN:", self.widget_dict['ff_fftdn'])
        filters_layout.addRow("FF Tempo:", self.widget_dict['ff_tempo'])
        filters_layout.addRow(self.widget_dict['ff_gate'])
        filters_layout.addRow(self.widget_dict['ff_speechnorm'])
        filters_layout.addRow(self.widget_dict['ff_loudnorm'])
        filters_layout.addRow("FF Silence Suppress (noise duration):", self.widget_dict['ff_silence_suppress'])
        filters_layout.addRow(self.widget_dict['ff_lowhighpass'])

        # Add all group boxes to advanced_expander
        adv_inner_layout = QVBoxLayout()
        adv_inner_layout.addWidget(diarize_box)
        adv_inner_layout.addWidget(decoding_box)
        adv_inner_layout.addWidget(vad_box)
        adv_inner_layout.addWidget(hallucination_box)
        adv_inner_layout.addWidget(extra_box)
        adv_inner_layout.addWidget(post_box)
        adv_inner_layout.addWidget(filters_box)

        advanced_form.addRow(adv_inner_layout)

        advanced_expander = Expander("Advanced & Additional Options", advanced_widget)
        container_layout.addWidget(advanced_expander)

        progress_layout = QHBoxLayout()
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        container_layout.addLayout(progress_layout)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.transcribe_button)
        button_layout.addWidget(self.save_button)
        container_layout.addLayout(button_layout)

        scroll_area.setWidget(container_widget)
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)

    def browse_files(self):
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Select Audio/Video Files", "/",
            "All Supported Files (*.wav *.mp3 *.m4a *.ogg *.mp4 *.mkv *.avi *.webm);;All Files (*.*)"
        )
        self.file_list_widget.addItems(filenames)

    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        self.widget_dict['output_dir'].setText(directory)

    def add_file_from_entry(self):
        file_path = self.file_entry.text().strip()
        if file_path:
            if validate_file_extension(file_path) or file_path.startswith(("http://", "https://")):
                self.file_list_widget.addItem(file_path)
                self.file_entry.clear()
            else:
                QMessageBox.warning(self, "Error", f"Invalid file path or unsupported file extension: {file_path}")
        else:
            QMessageBox.warning(self, "Error", "Input cannot be empty.")

    def clear_files(self):
        self.file_list_widget.clear()

    def load_settings(self):
        # Load all settings similarly to how you did before
        def load_bool(key, default='False'):
            return config.get_boolean('Settings', key, fallback=(default=='True'))
        def load_str(key, default=''):
            return config.get('Settings', key, fallback=default)

        self.widget_dict['language'].setCurrentText(load_str('language', DEFAULT_VALUES['language']))
        self.widget_dict['model'].setCurrentText(load_str('model', DEFAULT_VALUES['model']))
        self.widget_dict['task'].setCurrentText(load_str('task', DEFAULT_VALUES['task']))

        saved_output_formats = load_str('output_format','txt').split()
        for fmt in self.widget_dict['output_formats']:
            self.widget_dict['output_formats'][fmt].setChecked(fmt in saved_output_formats)

        self.widget_dict['output_dir'].setText(load_str('output_dir',''))
        self.widget_dict['ff_mdx_kim2'].setChecked(load_bool('ff_mdx_kim2','True'))
        self.widget_dict['vad_filter'].setChecked(load_bool('vad_filter','True'))
        self.widget_dict['vad_method'].setCurrentText(load_str('vad_method',DEFAULT_VALUES['vad_method']))
        self.widget_dict['word_timestamps'].setChecked(load_bool('word_timestamps','True'))
        self.widget_dict['temperature'].setText(load_str('temperature',DEFAULT_VALUES['temperature']))
        self.widget_dict['beam_size'].setText(load_str('beam_size',DEFAULT_VALUES['beam_size']))
        self.widget_dict['best_of'].setText(load_str('best_of',DEFAULT_VALUES['best_of']))
        self.widget_dict['mdx_chunk'].setText(load_str('mdx_chunk',DEFAULT_VALUES['mdx_chunk']))
        self.widget_dict['mdx_device'].setText(load_str('mdx_device',DEFAULT_VALUES['mdx_device']))
        self.widget_dict['compute_type'].setCurrentText(load_str('compute_type',DEFAULT_VALUES['compute_type']))
        self.widget_dict['enable_logging'].setChecked(load_bool('enable_logging','True'))
        self.widget_dict['sentence'].setChecked(load_bool('sentence','False'))
        self.widget_dict['exe_path'].setText(load_str('exe_path',DEFAULT_VALUES['exe_path']))

        self.widget_dict['diarize'].setChecked(load_bool('diarize','False'))
        self.widget_dict['diarize_method'].setCurrentText(load_str('diarize_method',DIARIZE_METHOD_OPTIONS[0]))
        self.widget_dict['num_speakers'].setText(load_str('num_speakers',''))
        self.widget_dict['min_speakers'].setText(load_str('min_speakers',''))
        self.widget_dict['max_speakers'].setText(load_str('max_speakers',''))
        self.widget_dict['diarize_dump'].setText(load_str('diarize_dump',''))
        self.widget_dict['hotwords'].setText(load_str('hotwords',''))
        self.widget_dict['rehot'].setChecked(load_bool('rehot','False'))

        ignore_val = load_str('ignore_dupe_prompt','2')
        self.widget_dict['ignore_dupe_prompt'].setText(ignore_val)

        multilingual_val = load_bool('multilingual','False')
        self.widget_dict['multilingual'].setChecked(multilingual_val)

        self.widget_dict['batch_size'].setText(load_str('batch_size',''))
        self.widget_dict['batched'].setChecked(load_bool('batched','False'))
        self.widget_dict['unmerged'].setChecked(load_bool('unmerged','False'))

        # Load new fields
        self.widget_dict['language_detection_threshold'].setText(load_str('language_detection_threshold','0.5'))
        self.widget_dict['language_detection_segments'].setText(load_str('language_detection_segments','1'))
        self.widget_dict['patience'].setText(load_str('patience','2.0'))
        self.widget_dict['length_penalty'].setText(load_str('length_penalty','1.0'))
        self.widget_dict['repetition_penalty'].setText(load_str('repetition_penalty','1.0'))
        self.widget_dict['no_repeat_ngram_size'].setText(load_str('no_repeat_ngram_size','0'))
        self.widget_dict['suppress_blank'].setChecked(load_bool('suppress_blank','True'))
        self.widget_dict['suppress_tokens'].setText(load_str('suppress_tokens','-1'))
        self.widget_dict['initial_prompt'].setText(load_str('initial_prompt','auto'))
        self.widget_dict['prefix'].setText(load_str('prefix',''))
        self.widget_dict['condition_on_previous_text'].setChecked(load_bool('condition_on_previous_text','True'))
        self.widget_dict['prompt_reset_on_temperature'].setText(load_str('prompt_reset_on_temperature','0.5'))
        self.widget_dict['without_timestamps'].setChecked(load_bool('without_timestamps','False'))
        self.widget_dict['max_initial_timestamp'].setText(load_str('max_initial_timestamp','1.0'))
        self.widget_dict['temperature_increment_on_fallback'].setText(load_str('temperature_increment_on_fallback','0.2'))
        self.widget_dict['compression_ratio_threshold'].setText(load_str('compression_ratio_threshold','2.4'))
        self.widget_dict['logprob_threshold'].setText(load_str('logprob_threshold','-1.0'))
        self.widget_dict['no_speech_threshold'].setText(load_str('no_speech_threshold','0.6'))

        self.widget_dict['highlight_words'].setChecked(load_bool('highlight_words','False'))
        self.widget_dict['prepend_punctuations'].setText(load_str('prepend_punctuations',"'“¿([{-)"))
        self.widget_dict['append_punctuations'].setText(load_str('append_punctuations',"'.。,，!！?？:：”)]}、)"))
        self.widget_dict['threads'].setText(load_str('threads','0'))

        self.widget_dict['vad_threshold'].setText(load_str('vad_threshold','0.45'))
        self.widget_dict['vad_min_speech_duration_ms'].setText(load_str('vad_min_speech_duration_ms','250'))
        self.widget_dict['vad_max_speech_duration_s'].setText(load_str('vad_max_speech_duration_s',''))
        self.widget_dict['vad_min_silence_duration_ms'].setText(load_str('vad_min_silence_duration_ms','3000'))
        self.widget_dict['vad_speech_pad_ms'].setText(load_str('vad_speech_pad_ms','900'))
        self.widget_dict['vad_window_size_samples'].setText(load_str('vad_window_size_samples','1536'))
        self.widget_dict['vad_dump'].setChecked(load_bool('vad_dump','False'))
        self.widget_dict['vad_dump_aud'].setChecked(load_bool('vad_dump_aud','False'))
        self.widget_dict['vad_device'].setText(load_str('vad_device','cuda'))

        self.widget_dict['hallucination_silence_threshold'].setText(load_str('hallucination_silence_threshold',''))
        self.widget_dict['hallucination_silence_th_temp'].setCurrentText(load_str('hallucination_silence_th_temp','1.0'))
        self.widget_dict['clip_timestamps'].setText(load_str('clip_timestamps','0'))

        self.widget_dict['max_new_tokens'].setText(load_str('max_new_tokens',''))
        self.widget_dict['chunk_length'].setText(load_str('chunk_length',''))

        self.widget_dict['postfix'].setChecked(load_bool('postfix','False'))
        self.widget_dict['skip'].setChecked(load_bool('skip','False'))
        self.widget_dict['beep_off'].setChecked(load_bool('beep_off','False'))
        self.widget_dict['check_files'].setChecked(load_bool('check_files','False'))
        self.widget_dict['alt_writer_off'].setChecked(load_bool('alt_writer_off','False'))
        self.widget_dict['hallucinations_list_off'].setChecked(load_bool('hallucinations_list_off','False'))
        self.widget_dict['v3_offsets_off'].setChecked(load_bool('v3_offsets_off','False'))
        self.widget_dict['prompt_reset_on_no_end'].setCurrentText(load_str('prompt_reset_on_no_end','2'))
        self.widget_dict['one_word'].setCurrentText(load_str('one_word','0'))
        self.widget_dict['standard'].setChecked(load_bool('standard','False'))
        self.widget_dict['standard_asia'].setChecked(load_bool('standard_asia','False'))
        self.widget_dict['max_comma'].setText(load_str('max_comma','250'))
        self.widget_dict['max_comma_cent'].setCurrentText(load_str('max_comma_cent','100'))
        self.widget_dict['max_gap'].setText(load_str('max_gap','3.0'))
        self.widget_dict['max_line_width'].setText(load_str('max_line_width','1000'))
        self.widget_dict['max_line_count'].setText(load_str('max_line_count','1'))
        self.widget_dict['min_dist_to_end'].setCurrentText(load_str('min_dist_to_end','0'))

        self.widget_dict['ff_dump'].setChecked(load_bool('ff_dump','False'))
        self.widget_dict['ff_track'].setCurrentText(load_str('ff_track','1'))
        self.widget_dict['ff_fc'].setChecked(load_bool('ff_fc','False'))
        self.widget_dict['ff_mp3'].setChecked(load_bool('ff_mp3','False'))
        self.widget_dict['ff_sync'].setChecked(load_bool('ff_sync','False'))
        self.widget_dict['ff_rnndn_sh'].setChecked(load_bool('ff_rnndn_sh','False'))
        self.widget_dict['ff_rnndn_xiph'].setChecked(load_bool('ff_rnndn_xiph','False'))
        self.widget_dict['ff_fftdn'].setText(load_str('ff_fftdn','0'))
        self.widget_dict['ff_tempo'].setText(load_str('ff_tempo','1.0'))
        self.widget_dict['ff_gate'].setChecked(load_bool('ff_gate','False'))
        self.widget_dict['ff_speechnorm'].setChecked(load_bool('ff_speechnorm','False'))
        self.widget_dict['ff_loudnorm'].setChecked(load_bool('ff_loudnorm','False'))
        self.widget_dict['ff_silence_suppress'].setText(load_str('ff_silence_suppress','0 3.0'))
        self.widget_dict['ff_lowhighpass'].setChecked(load_bool('ff_lowhighpass','False'))

        self.widget_dict['diarize_device'].setText(load_str('diarize_device','cuda'))
        self.widget_dict['diarize_threads'].setText(load_str('diarize_threads','0'))
        self.widget_dict['speaker'].setText(load_str('speaker','SPEAKER'))

    def start_transcription(self):
        file_list = [self.file_list_widget.item(i).text() for i in range(self.file_list_widget.count())]

        self.transcribe_button.setEnabled(False)
        self.save_button.setEnabled(False)

        self.transcription_worker = TranscriptionWorker(file_list, self.widget_dict)
        self.transcription_worker.progress_updated.connect(self.update_progress)
        self.transcription_worker.finished.connect(self.transcription_finished)
        self.transcription_worker.error_occurred.connect(self.show_error_message)
        self.transcription_worker.start()

    def update_progress(self, progress, message):
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)

    def transcription_finished(self):
        QMessageBox.information(self, "Success", "Transcription completed for all files!")
        if enable_logging():
            logging.info("Transcription completed for all files.")
        self.reset_progress()
        self.transcribe_button.setEnabled(True)
        self.save_button.setEnabled(True)

    def show_error_message(self, error_message):
        QMessageBox.critical(self, "Error", error_message)
        if enable_logging():
            logging.error(error_message)
        self.reset_progress()
        self.transcribe_button.setEnabled(True)
        self.save_button.setEnabled(True)

    def reset_progress(self):
        self.progress_bar.setValue(0)
        self.progress_label.setText("Progress: 0/0")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if os.path.isfile(file_path) and validate_file_extension(file_path):
                    self.file_list_widget.addItem(file_path)
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pixmap = QPixmap()
    pixmap.loadFromData(base64.b64decode(base64_icon))
    app.setWindowIcon(QIcon(pixmap))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
