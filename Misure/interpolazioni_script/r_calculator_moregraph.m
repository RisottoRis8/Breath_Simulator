%% Caratterizzazione PNT - OTTIMIZZATO (3 Grafici 2D con Interpolazione)
clear; clc; close all;

% --- PARAMETRI DI CONFIGURAZIONE ---
metodo_interp = 'pchip'; % Tipo di interpolazione scelta
n_factor = 20;           % Risoluzione delle curve (n_factor * num_punti)
s_inf = 0.25; s_sup = 0.80; % Soglie per isolare il plateau stabile
w_smooth = 15;             % Finestra per comprimere il rumore (moving average)

% --- SELEZIONE CARTELLA ---
path_cartella = uigetdir('', 'Seleziona cartella con i file CSV');
if isequal(path_cartella, 0), return; end
lista_file = dir(fullfile(path_cartella, 'misura*.csv'));

risultati = []; % Matrice [P_rep, Q_rep, R_rep]

fprintf('\n%-35s | %-10s | %-10s | %-10s\n', 'File Analizzato', 'P [Pa]', 'Q [L/s]', 'R [Pa*s/L]');
fprintf('----------------------------------------------------------------------------\n');

for i = 1:length(lista_file)
    fn = fullfile(path_cartella, lista_file(i).name);
    
    % 1. Estrazione Volume dai Metadati
    v_siringa = NaN;
    fid = fopen(fn, 'r');
    while ~feof(fid)
        linea = fgetl(fid);
        if ~ischar(linea), break; end
        if contains(linea, 'Capacita', 'IgnoreCase', true)
            parti = strsplit(linea, ',');
            v_siringa = str2double(parti{2});
        end
        if contains(linea, 'Time_s'), break; end
    end
    fclose(fid);
    if isnan(v_siringa), continue; end

    % 2. Lettura Dati
    try
        data_raw = readmatrix(fn);
        data_raw(any(isnan(data_raw), 2), :) = []; 
        t = data_raw(:, 1); p = data_raw(:, 2);
        [t, idx] = unique(t); p = p(idx);
        
        % 3. Calcolo Flusso Istantaneo e Filtraggio Robusto
        area_p = trapz(t, p);
        q_ist = (v_siringa .* p) ./ area_p; 
        
        p_max = max(p);
        idx_v = find(p >= p_max * s_inf & p <= p_max * s_sup);
        
        if length(idx_v) > w_smooth
            % Compressione dati (Media Mobile manuale)
            p_f = conv(p(idx_v), ones(w_smooth,1)/w_smooth, 'valid');
            q_f = conv(q_ist(idx_v), ones(w_smooth,1)/w_smooth, 'valid');
            
            % Media Robusta (Manuale)
            p_rep = manual_trimmean(p_f, 15);
            q_rep = manual_trimmean(q_f, 15);
            r_rep = p_rep / q_rep;
            
            risultati = [risultati; p_rep, q_rep, r_rep];
            fprintf('%-35s | %10.2f | %10.3f | %10.3f\n', lista_file(i).name, p_rep, q_rep, r_rep);
        end
    catch
        continue;
    end
end

num_p = size(risultati, 1);
fprintf('----------------------------------------------------------------------------\n');
fprintf('ANALISI COMPLETATA\n');
fprintf('Numero di punti di resistenza calcolati: %d\n', num_p);
fprintf('----------------------------------------------------------------------------\n\n');

if num_p < 2, error('Dati insufficienti per generare le interpolazioni.'); end

% --- PREPARAZIONE DATI PER INTERPOLAZIONE ---
P = risultati(:,1); Q = risultati(:,2); R = risultati(:,3);

% Ordinamento per flusso (per grafici R-Q e P-Q)
[Q_s, iQ] = sort(Q); 
R_sQ = R(iQ); 
P_sQ = P(iQ);

% Ordinamento per pressione (per grafico R-P)
[P_s, iP] = sort(P); 
R_sP = R(iP);

% Vettori densi per le curve
q_vec = linspace(min(Q), max(Q), num_p * n_factor);
p_vec = linspace(min(P), max(P), num_p * n_factor);

% --- GRAFICA 2D ---
figure('Color', 'w', 'Position', [100 100 1300 450]);

% 1. Resistenza vs Flusso
subplot(1,3,1);
plot(Q, R, 'ko', 'MarkerFaceColor', 'r', 'DisplayName', 'Dati Mediati'); hold on;
plot(q_vec, interp1(Q_s, R_sQ, q_vec, metodo_interp), 'r-', 'LineWidth', 2, 'DisplayName', 'Interpolazione');
grid on; xlabel('Flusso Q [L/s]'); ylabel('Resistenza R [Pa*s/L]');
title('Resistenza vs Flusso'); legend('Location', 'best');

% 2. Resistenza vs Pressione
subplot(1,3,2);
plot(P, R, 'ko', 'MarkerFaceColor', 'g', 'DisplayName', 'Dati Mediati'); hold on;
plot(p_vec, interp1(P_s, R_sP, p_vec, metodo_interp), 'g-', 'LineWidth', 2, 'DisplayName', 'Interpolazione');
grid on; xlabel('Pressione P [Pa]'); ylabel('Resistenza R [Pa*s/L]');
title('Resistenza vs Pressione'); legend('Location', 'best');

% 3. Pressione vs Flusso (Sostituita lsline con interpolazione)
subplot(1,3,3);
plot(Q, P, 'ko', 'MarkerFaceColor', 'b', 'DisplayName', 'Dati Mediati'); hold on;
plot(q_vec, interp1(Q_s, P_sQ, q_vec, metodo_interp), 'b-', 'LineWidth', 2, 'DisplayName', 'Curva P-Q');
grid on; xlabel('Flusso Q [L/s]'); ylabel('Pressione P [Pa]');
title('Relazione Pressione-Flusso'); legend('Location', 'best');

sgtitle(['Caratterizzazione Pneumotacografo - ' num2str(num_p) ' Misure Elaborate'], 'FontSize', 14);

%% --- FUNZIONI DI SUPPORTO ---
function m = manual_trimmean(data, percent)
    n = length(data); k = max(1, round(n * (percent/100) / 2));
    if n <= 2*k, m = mean(data); return; end
    s = sort(data); m = mean(s(k+1 : end-k));
end