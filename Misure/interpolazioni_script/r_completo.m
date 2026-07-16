%% Caratterizzazione PNT - RAW (Arancione) vs OTTIMIZZATO (Rosso)
clear; clc; close all;

% =========================================================================
% --- FLAG DI VISUALIZZAZIONE ---
mostra_raw         = true;  % true per vedere i dati grezzi (Arancione)
mostra_ottimizzato = true;  % true per vedere i dati ottimizzati (Rosso)
% =========================================================================

% --- PARAMETRI DI CONFIGURAZIONE ---
metodo_interp = 'pchip'; 
n_factor = 20; 
s_inf = 0.25; s_sup = 0.80; % Soglie plateau
w_smooth = 15;             % Finestra compressione rumore

% --- SELEZIONE CARTELLA ---
path_cartella = uigetdir('', 'Seleziona cartella con i file CSV');
if isequal(path_cartella, 0), return; end
lista_file = dir(fullfile(path_cartella, 'misura*.csv'));

res_raw = []; % [P, Q, R]
res_opt = []; % [P, Q, R]

fprintf('\n%-35s | %-12s | %-12s\n', 'File Analizzato', 'R RAW', 'R OTT.');
fprintf('----------------------------------------------------------------------------\n');

for i = 1:length(lista_file)
    fn = fullfile(path_cartella, lista_file(i).name);
    
    % 1. Estrazione Volume
    v_s = NaN; fid = fopen(fn, 'r');
    while ~feof(fid)
        l = fgetl(fid); if ~ischar(l), break; end
        if contains(l, 'Capacita', 'IgnoreCase', true)
            parti = strsplit(l, ','); v_s = str2double(parti{2});
        end
        if contains(l, 'Time_s'), break; end
    end
    fclose(fid);
    if isnan(v_s), continue; end

    % 2. Lettura Dati
    try
        data = readmatrix(fn);
        data(any(isnan(data), 2), :) = []; 
        t = data(:, 1); p = data(:, 2);
        [t, idx] = unique(t); p = p(idx);
        if length(t) < 2, continue; end

        % --- CALCOLO RAW (Lineare Puro) ---
        p_raw_avg = mean(p);
        q_raw_avg = v_s / (t(end) - t(1));
        res_raw = [res_raw; p_raw_avg, q_raw_avg, p_raw_avg/q_raw_avg];

        % --- CALCOLO OTTIMIZZATO (Robust) ---
        q_ist = (v_s .* p) ./ trapz(t, p);
        idx_v = find(p >= max(p)*s_inf & p <= max(p)*s_sup);
        
        if length(idx_v) > w_smooth
            p_f = conv(p(idx_v), ones(w_smooth,1)/w_smooth, 'valid');
            q_f = conv(q_ist(idx_v), ones(w_smooth,1)/w_smooth, 'valid');
            p_o = manual_trimmean(p_f, 15);
            q_o = manual_trimmean(q_f, 15);
            res_opt = [res_opt; p_o, q_o, p_o/q_o];
            fprintf('%-35s | %12.3f | %12.3f\n', lista_file(i).name, p_raw_avg/q_raw_avg, p_o/q_o);
        else
            fprintf('%-35s | %12.3f | %12s\n', lista_file(i).name, p_raw_avg/q_raw_avg, 'Sotto-soglia');
        end
    catch
        continue;
    end
end

% --- GRAFICA ---
if isempty(res_raw) && isempty(res_opt), error('Nessun dato estratto.'); end

figure('Color', 'w', 'Position', [50 50 1400 500]);
titoli = {'Resistenza vs Flusso', 'Resistenza vs Pressione', 'Pressione vs Flusso'};
e_x = {'Flusso Q [L/s]', 'Pressione P [Pa]', 'Flusso Q [L/s]'};
e_y = {'Resistenza R [Pa*s/L]', 'Resistenza R [Pa*s/L]', 'Pressione P [Pa]'};

% Colori definiti
col_raw = [1, 0.5, 0]; % Arancione RGB
col_opt = [1, 0, 0];   % Rosso RGB

for ax = 1:3
    subplot(1,3,ax); hold on; grid on; box on;
    xlabel(e_x{ax}); ylabel(e_y{ax}); title(titoli{ax});
    
    % --- PLOT RAW (ARANCIONE) ---
    if mostra_raw && ~isempty(res_raw)
        if ax == 1, X = res_raw(:,2); Y = res_raw(:,3);
        elseif ax == 2, X = res_raw(:,1); Y = res_raw(:,3);
        else, X = res_raw(:,2); Y = res_raw(:,1);
        end
        [Xs, idx] = sort(X); Ys = Y(idx);
        Xv = linspace(min(Xs), max(Xs), 100);
        plot(X, Y, 'o', 'Color', col_raw, 'MarkerFaceColor', col_raw, 'MarkerSize', 4, 'DisplayName', 'Dati RAW');
        plot(Xv, interp1(Xs, Ys, Xv, metodo_interp), 'Color', col_raw, 'LineWidth', 1.5, 'DisplayName', 'Interp. RAW');
    end
    
    % --- PLOT OTTIMIZZATO (ROSSO) ---
    if mostra_ottimizzato && ~isempty(res_opt)
        if ax == 1, X = res_opt(:,2); Y = res_opt(:,3);
        elseif ax == 2, X = res_opt(:,1); Y = res_opt(:,3);
        else, X = res_opt(:,2); Y = res_opt(:,1);
        end
        [Xs, idx] = sort(X); Ys = Y(idx);
        Xv = linspace(min(Xs), max(Xs), 100);
        plot(X, Y, 'o', 'Color', col_opt, 'MarkerFaceColor', col_opt, 'MarkerSize', 4, 'DisplayName', 'Dati OTT.');
        plot(Xv, interp1(Xs, Ys, Xv, metodo_interp), 'Color', col_opt, 'LineWidth', 2, 'DisplayName', 'Interp. OTT.');
    end
    legend('Location', 'best', 'FontSize', 8);
end

sgtitle('Confronto PNT: RAW (Arancione) vs OTTIMIZZATO (Rosso)', 'FontSize', 14);

%% --- FUNZIONI LOCALI ---
function m = manual_trimmean(data, percent)
    n = length(data); k = max(1, round(n * (percent/100) / 2));
    if n <= 2*k, m = mean(data); return; end
    s = sort(data); m = mean(s(k+1 : end-k));
end