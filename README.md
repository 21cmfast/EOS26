# EOS25
All scipts required to reproduce the EOS25 simulation

<table><thead>
  <tr>
    <th>EOS25 simulation step<br></th>
    <th colspan="2">Computation time [hrs]</th>
    <th colspan="2">Memory [Tb]</th>
    <th colspan="2">Storage [Tb]</th>
    <th colspan="2">SUs</th>
  </tr></thead>
<tbody>
  <tr>
    <td></td>
    <td>Estimated</td>
    <td>Actual</td>
    <td>Estimated</td>
    <td>Actual</td>
    <td>Estimated</td>
    <td>Actual</td>
    <td>Estimated</td>
    <td>Actual</td>
  </tr>
  <tr>
    <td>Initial conditions</td>
    <td>13.5 + 2.75 <br>for writing to disk<br><br></td>
    <td></td>
    <td>1.1</td>
    <td>1.3</td>
    <td>652 Gb</td>
    <td>747 Gb</td>
    <td></td>
    <td>864 EM <br> for ICs + PFs<br></td>
  </tr>
  <tr>
    <td>One perturbed field<br></td>
    <td>0.6<br></td>
    <td></td>
    <td>25 Gb<br></td>
    <td>26 Gb</td>
    <td>25Gb x 92 = 2.3Tb</td>
    <td>2.4Tb</td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td>22 hrs</td>
    <td></td>
    <td>0.71</td>
    <td>0.77</td>
    <td>~330 G</td>
    <td>33 G</td>
    <td>720 EM</td>
    <td>617 EM</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td>7</td>
    <td></td>
    <td>3.65</td>
    <td></td>
    <td>2.6Tb x 92 = 240 Tb<br>0.215 x 92 = 20Tb without XRS<br></td>
    <td></td>
    <td>672 EM x 92 = 62k</td>
    <td></td>
  </tr>
</tbody></table>
