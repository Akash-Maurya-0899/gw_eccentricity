"""
Base module to measure eccentricity and mean anomaly for given waveform data.

Part of Defining eccentricity project
Md Arif Shaikh, Mar 29, 2022
"""

import numpy as np
from scipy.interpolate import InterpolatedUnivariateSpline
from .utils import get_peak_via_quadratic_fit, check_kwargs_and_set_defaults
import warnings


class eccDefinition:
    """Measure eccentricity from given waveform data dictionary."""

    def __init__(self, dataDict):
        """Init eccDefinition class.

        parameters:
        ---------
        dataDict: dictionary containing waveform modes dict, time etc
        should follow the format {"t": time, "hlm": modeDict, ..}
        and modeDict = {(l, m): hlm_mode_data}
        for ResidualAmplitude method, provide "t_zeroecc" and "hlm_zeroecc"
        as well in the dataDict.
        """
        self.dataDict = dataDict
        self.t = self.dataDict["t"]
        self.hlm = self.dataDict["hlm"]
        self.h22 = self.hlm[(2, 2)]
        self.amp22 = np.abs(self.h22)
        # shift the time axis to make t = 0 at merger
        # t_ref would be then negative. This helps
        # when subtracting quasi circular amplitude from
        # eccentric amplitude in residual amplitude method
        self.t = self.t - get_peak_via_quadratic_fit(
            self.t, self.amp22)[0]
        self.phase22 = - np.unwrap(np.angle(self.h22))
        self.omega22 = np.gradient(self.phase22, self.t)

    def find_extrema(self, which="maxima", extrema_finding_kwargs=None):
        """Find the extrema in the data.

        parameters:
        -----------
        which: either maxima, peaks, minima or troughs
        extrema_finding_kwargs: Dictionary of arguments to be passed to the
        peak finding function.

        returns:
        ------
        array of positions of extrema.
        """
        raise NotImplementedError("Please override me.")

    def interp_extrema(self, which="maxima", extrema_finding_kwargs=None,
                       spline_kwargs=None,
                       num_orbits_to_exclude_before_merger=1):
        """Interpolator through extrema.

        parameters:
        -----------
        which: either maxima, peaks, minima or troughs
        extrema_finding_kwargs: Dictionary of arguments to be passed to the
        peak finding function.
        spline_kwargs: arguments to be passed to InterpolatedUnivariateSpline
        num_orbits_to_exclude_before_merger:
              could be either None or non negative real number. If None, then
              the full data even after merger is used but this might cause
              issues with he interpolaion trough exrema. For non negative real
              number, that many orbits prior to merger is exculded.
              Default is 1.

        returns:
        ------
        spline through extrema, positions of extrema
        """
        extrema_idx = self.find_extrema(which, extrema_finding_kwargs)
        # experimenting wih throwing away peaks too close to merger
        # This helps in avoiding unwanted feature in the spline
        # thorugh the extrema
        if num_orbits_to_exclude_before_merger is not None:
            merger_idx = np.argmin(np.abs(self.t))
            phase22_at_merger = self.phase22[merger_idx]
            # one orbit changes the 22 mode phase by 4 pi since
            # omega22 = 2 omega_orb
            phase22_num_orbits_earlier_than_merger = (
                phase22_at_merger
                - 4 * np.pi
                * num_orbits_to_exclude_before_merger)
            idx_num_orbit_earlier_than_merger = np.argmin(np.abs(
                self.phase22 - phase22_num_orbits_earlier_than_merger))
            # use only the extrema those are atleast num_orbits away from the
            # merger to avoid unphysical features like nonmonotonic
            # eccentricity near the merger
            extrema_idx = extrema_idx[extrema_idx
                                      <= idx_num_orbit_earlier_than_merger]
        if len(extrema_idx) >= 2:
            spline = InterpolatedUnivariateSpline(self.t[extrema_idx],
                                                  self.omega22[extrema_idx],
                                                  **spline_kwargs)
            return spline, extrema_idx
        else:
            raise Exception(
                f"Sufficient number of {which} are not found."
                " Can not create an interpolator.")

    def measure_ecc(self, tref_in, extrema_finding_kwargs=None,
                    spline_kwargs=None, extra_kwargs=None):
        """Measure eccentricity and mean anomaly at reference time.

        parameters:
        ----------
        tref_in:
              Input reference time to measure eccentricity and mean anomaly.
              This is the input array provided by the user to evaluate
              eccenricity and mean anomaly at. However, if
              num_orbits_to_exclude_before_merger is not None, then the
              interpolator used to measure eccentricty is constructed using
              extrema only upto num_orbits_to_exclude_before_merger and
              accorindly a tmax is set by chosing the min of time of last
              peak/trough. Thus the eccentricity and mean anomaly are computed
              only upto tmax and a new time array tref_out is returned with
              max(tref_out) = tmax

        extrema_finding_kwargs:
             Dictionary of arguments to be passed to the
             peak finding function.

        spline_kwargs:
             arguments to be passed to InterpolatedUnivariateSpline

        extra_kwargs:
            any extra kwargs to be passed. Allowed kwargs are

            num_orbits_to_exclude_before_merger:
              could be either None or non negative real number. If None, then
              the full data even after merger is used but this might cause
              issues with he interpolaion trough exrema. For non negative real
              number, that many orbits prior to merger is exculded.
              Default is 1.
           debug:
              Check if the measured eccentricity is monotonic and concave.
              Default value is True

        returns:
        --------
        tref_out: array of reference time where eccenricity and mean anomaly is
              measured. This would be different from tref_in if
              exclude_num_obrits_before_merger in the extra_kwargs
              is not None

        ecc_ref: measured eccentricity at tref_out
        mean_ano_ref: measured mean anomaly at tref_out
        """
        tref_in = np.atleast_1d(tref_in)
        if any(tref_in >= 0):
            raise Exception("Reference time must be negative. Merger being"
                            " at t = 0.")
        default_spline_kwargs = {"w": None,
                                 "bbox": [None, None],
                                 "k": 3,
                                 "ext": 0,
                                 "check_finite": False}
        # make it iterable
        if spline_kwargs is None:
            spline_kwargs = {}

        # Sanity check for spline kwargs and set default values
        spline_kwargs = check_kwargs_and_set_defaults(
            spline_kwargs, default_spline_kwargs,
            "spline_kwargs")

        self.spline_kwargs = spline_kwargs

        if extra_kwargs is None:
            extra_kwargs = {}
        default_extra_kwargs = {"num_orbits_to_exclude_before_merger": 1,
                                "debug": True}
        # sanity check for extra kwargs and set to default values
        extra_kwargs = check_kwargs_and_set_defaults(
            extra_kwargs, default_extra_kwargs,
            "extra_kwargs")
        if default_extra_kwargs["num_orbits_to_exclude_before_merger"] < 0:
            raise ValueError(
                "num_orbits_to_exclude_before_merger must be non-negative. "
                "Given value was "
                f"{default_extra_kwargs['num_orbits_to_exclude_before_merger']}")
        self.extra_kwargs = extra_kwargs

        omega_peaks_interp, self.peaks_location = self.interp_extrema(
            "maxima", extrema_finding_kwargs, spline_kwargs,
            extra_kwargs["num_orbits_to_exclude_before_merger"])
        omega_troughs_interp, self.troughs_location = self.interp_extrema(
            "minima", extrema_finding_kwargs, spline_kwargs,
            extra_kwargs["num_orbits_to_exclude_before_merger"])

        t_peaks = self.t[self.peaks_location]
        if extra_kwargs["num_orbits_to_exclude_before_merger"] is not None:
            t_troughs = self.t[self.troughs_location]
            t_max = min(t_peaks[-1], t_troughs[-1])
            # measure eccentricty and mean anomaly only upto t_max
            tref_out = tref_in[tref_in <= t_max]
        else:
            tref_out = tref_in
        # check if the tref_out has a peak before and after
        # This required to define mean anomaly.
        if tref_out[0] < t_peaks[0] or tref_out[-1] >= t_peaks[-1]:
            raise Exception("Reference time must be within two peaks.")

        # compute eccentricty from the value of omega_peaks_interp
        # and omega_troughs_interp at tref_out using the fromula in
        # ref. arXiv:2101.11798 eq. 4
        self.omega_peak_at_tref_out = omega_peaks_interp(tref_out)
        self.omega_trough_at_tref_out = omega_troughs_interp(tref_out)
        ecc_ref = ((np.sqrt(self.omega_peak_at_tref_out)
                    - np.sqrt(self.omega_trough_at_tref_out))
                   / (np.sqrt(self.omega_peak_at_tref_out)
                      + np.sqrt(self.omega_trough_at_tref_out)))

        @np.vectorize
        def compute_mean_ano(time):
            """
            Compute mean anomaly.

            Compute the mean anomaly using Eq.7 of arXiv:2101.11798.
            Mean anomaly grows linearly in time from 0 to 2 pi over
            the range [t_at_last_peak, t_at_next_peak], where t_at_last_peak
            is the time at the previous periastron, and t_at_next_peak is
            the time at the next periastron.
            """
            idx_at_last_peak = np.where(t_peaks <= time)[0][-1]
            t_at_last_peak = t_peaks[idx_at_last_peak]
            t_at_next_peak = t_peaks[idx_at_last_peak + 1]
            t_since_last_peak = time - t_at_last_peak
            current_period = t_at_next_peak - t_at_last_peak
            mean_ano_ref = 2 * np.pi * t_since_last_peak / current_period
            return mean_ano_ref

        # Compute mean anomaly at tref_out
        mean_ano_ref = compute_mean_ano(tref_out)

        if len(tref_out) == 1:
            mean_ano_ref = mean_ano_ref[0]
            ecc_ref = ecc_ref[0]

        # check if eccenricity is monotonic and convex
        if len(tref_out) > 1 and extra_kwargs["debug"]:
            self.check_monotonicity_and_convexity(tref_out, ecc_ref)

        return tref_out, ecc_ref, mean_ano_ref

    def check_monotonicity_and_convexity(self, tref_out, ecc_ref,
                                         check_convexity=False,
                                         t_for_ecc_test=None):
        """Check if measured eccentricity is monotonic.

        parameters:
        tref_out: Output reference time from eccentricty measurement
        ecc_ref: measured eccentricity at tref_out
        check_convexity: In addition to monotonicity, it will check for
        convexity as well. Default is False.
        t_for_ecc_test: Time array to build a spline. If Noe, then uses
        a new time array with delta_t = 0.1 for same range as in tref_out
        Default is None.
        """
        spline = InterpolatedUnivariateSpline(tref_out, ecc_ref)
        if t_for_ecc_test is None:
            t_for_ecc_test = np.arange(tref_out[0], tref_out[-1], 0.1)
            len_t_for_ecc_test = len(t_for_ecc_test)
            if len_t_for_ecc_test > 100000:
                warnings.warn("time array t_for_ecc_test is too long."
                              f" Length is {len_t_for_ecc_test}")
        dEccDt = spline.derivative(n=1)
        dEccs = dEccDt(t_for_ecc_test)
        self.t_for_ecc_test = t_for_ecc_test
        self.decc_dt = dEccs
        if any(dEccs > 0):
            warnings.warn("Eccentricity has non monotonicity.")
        if check_convexity:
            d2EccDt = spline.derivative(n=2)
            d2Eccs = d2EccDt(t_for_ecc_test)
            self.d2ecc_dt = d2Eccs
            if any(d2Eccs > 0):
                warnings.warn("Eccentricity has concavity.")
