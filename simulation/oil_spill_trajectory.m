%% AquaGuard: Oil Spill Trajectory Simulation — 48h Forecast
% Lagrangian particle tracking model for surface oil transport
% Based on GNOME (NOAA General Operational Modeling Environment) methodology
%
% Parameters:
%   Spill location: Adriatic Sea near Bari (~43°N, 14.5°E)
%   Wind: 5 m/s eastward, 2 m/s northward
%   Current: 0.2 m/s eastward, 0.1 m/s northward
%   Duration: 48 hours, dt = 1 hour
%   Particles: 200
%   Diffusion: 1.0 m²/s

clear; clc; close all;

rng(42);  % reproducibility

%% Parameters
n_particles   = 200;
dt_h          = 1;           % time step [hours]
duration_h    = 48;
n_steps       = duration_h / dt_h + 1;
wind_factor   = 0.03;        % 3% wind-to-surface-drift

% Spill origin (lon, lat)
spill_lon = 14.50;
spill_lat = 43.20;

% Forcing
u_wind = 5.0;   % m/s eastward
v_wind = 2.0;   % m/s northward
u_cur  = 0.20;  % m/s eastward
v_cur  = 0.10;  % m/s northward

% Diffusion
D = 1.0;                          % m²/s
sigma_m = sqrt(2 * D * dt_h * 3600);  % std per step [m]

% Coordinate conversions (at spill_lat)
m_per_deg_lat = 111320;
m_per_deg_lon = 111320 * cosd(spill_lat);

%% Initialise particles
lons = spill_lon * ones(n_particles, n_steps);
lats = spill_lat * ones(n_particles, n_steps);

%% Effective velocity [deg/step]
u_total = wind_factor * u_wind + u_cur;  % m/s
v_total = wind_factor * v_wind + v_cur;  % m/s
d_lon_step = (u_total * dt_h * 3600) / m_per_deg_lon;
d_lat_step = (v_total * dt_h * 3600) / m_per_deg_lat;

sigma_lon = sigma_m / m_per_deg_lon;
sigma_lat = sigma_m / m_per_deg_lat;

%% Integrate forward
for t = 1:(n_steps - 1)
    noise_lon = sigma_lon * randn(n_particles, 1);
    noise_lat = sigma_lat * randn(n_particles, 1);
    lons(:, t+1) = lons(:, t) + d_lon_step + noise_lon;
    lats(:, t+1) = lats(:, t) + d_lat_step + noise_lat;
end

%% Compute uncertainty ellipse (1-sigma) at each step
std_lon = std(lons, 0, 1);
std_lat = std(lats, 0, 1);
unc_km  = sqrt((std_lon * m_per_deg_lon / 1000).^2 + ...
               (std_lat * m_per_deg_lat / 1000).^2);

%% Select plot snapshots: 0h, 12h, 24h, 48h
snap_steps = [1, 13, 25, 49];
snap_labels = {'T+0h', 'T+12h', 'T+24h', 'T+48h'};
colors = [0.2 0.6 1.0;
          0.1 0.9 0.5;
          1.0 0.6 0.1;
          0.9 0.2 0.2];

%% ─── Figure ───────────────────────────────────────────────
fig = figure('Color', [0.04 0.08 0.16], ...
             'Position', [100 100 1100 700]);
ax = axes('Parent', fig, 'Color', [0.06 0.12 0.22], ...
          'XColor', [0.8 0.9 1], 'YColor', [0.8 0.9 1], ...
          'GridColor', [0.3 0.4 0.5], 'GridAlpha', 0.3);
hold(ax, 'on'); grid(ax, 'on');

%% Plot all particle trajectories (faint)
for p = 1:n_particles
    plot(ax, lons(p,:), lats(p,:), '-', ...
         'Color', [0.3 0.5 0.8 0.08], 'LineWidth', 0.5);
end

%% Plot snapshots
h_snap = gobjects(length(snap_steps), 1);
for s = 1:length(snap_steps)
    t = snap_steps(s);
    c = colors(s, :);
    scatter(ax, lons(:,t), lats(:,t), 12, c, 'filled', ...
            'MarkerFaceAlpha', 0.7);
    % Centroid
    cx = mean(lons(:,t)); cy = mean(lats(:,t));
    h_snap(s) = scatter(ax, cx, cy, 80, c, 'filled', 'd', ...
                        'MarkerEdgeColor', 'w', 'LineWidth', 1.5);
end

%% Plot uncertainty ellipse at T+48h
t48 = snap_steps(end);
cx48 = mean(lons(:,t48));
cy48 = mean(lats(:,t48));
rx = std_lon(t48) * 2;     % 2-sigma in degrees
ry = std_lat(t48) * 2;
theta = linspace(0, 2*pi, 120);
ell_lon = cx48 + rx * cos(theta);
ell_lat = cy48 + ry * sin(theta);
plot(ax, ell_lon, ell_lat, '--', 'Color', [1 0.4 0.1 0.9], ...
     'LineWidth', 1.5);

%% Wind arrow
quiver(ax, spill_lon - 0.3, spill_lat + 0.25, ...
       u_wind * 0.005, v_wind * 0.005, 0, ...
       'Color', [0.6 0.9 1], 'LineWidth', 2, ...
       'MaxHeadSize', 3);
text(ax, spill_lon - 0.28, spill_lat + 0.30, ...
     sprintf('Wind %.0f m/s', hypot(u_wind, v_wind)), ...
     'Color', [0.6 0.9 1], 'FontSize', 9);

%% Spill origin marker
scatter(ax, spill_lon, spill_lat, 120, 'r', 'x', 'LineWidth', 3);
text(ax, spill_lon + 0.03, spill_lat - 0.03, 'SPILL ORIGIN', ...
     'Color', 'r', 'FontSize', 9, 'FontWeight', 'bold');

%% Labels and formatting
xlabel(ax, 'Longitude (°E)', 'FontSize', 12, 'Color', [0.8 0.9 1]);
ylabel(ax, 'Latitude (°N)',  'FontSize', 12, 'Color', [0.8 0.9 1]);
title(ax, 'AquaGuard: Oil Spill Trajectory Simulation — 48h Forecast', ...
      'FontSize', 14, 'FontWeight', 'bold', 'Color', [0 0.85 1]);
subtitle(ax, sprintf(['Adriatic Sea — %d particles — Wind %.0f m/s  |  ' ...
         'Current %.2f m/s  |  D=%.1f m²/s'], ...
         n_particles, hypot(u_wind,v_wind), hypot(u_cur,v_cur), D), ...
         'Color', [0.6 0.7 0.8], 'FontSize', 10);

legend(ax, h_snap, snap_labels, ...
       'TextColor', [0.8 0.9 1], 'Color', [0.06 0.12 0.22], ...
       'EdgeColor', [0.3 0.5 0.7], 'Location', 'northwest', 'FontSize', 10);

ax.XAxis.TickLabelColor = [0.7 0.85 1];
ax.YAxis.TickLabelColor = [0.7 0.85 1];

%% Uncertainty text box
unc_str = sprintf('48h uncertainty radius: %.1f km', unc_km(end));
annotation('textbox', [0.65 0.03 0.30 0.06], 'String', unc_str, ...
           'Color', [1 0.5 0.1], 'BackgroundColor', [0.04 0.08 0.16], ...
           'EdgeColor', [1 0.5 0.1], 'FontSize', 10, 'FontWeight', 'bold', ...
           'HorizontalAlignment', 'center');

%% Save
saveas(fig, 'oil_spill_forecast.png');
fprintf('Saved: oil_spill_forecast.png\n');
fprintf('48h centroid: %.4f°E, %.4f°N\n', mean(lons(:,end)), mean(lats(:,end)));
fprintf('Uncertainty radius at 48h: %.1f km\n', unc_km(end));
