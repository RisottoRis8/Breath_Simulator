%% Caratterizzazione Pneumotacografo - Versione Finale con Log Punti
clear; clc; close all;

% --- CONFIGURAZIONE ---
metodo_interp = 'pchip'; 
n_factor = 15;
soglia_inf = 0.25;       % Finestra centrale per eliminare startup/rampdown
soglia_sup = 0.80;       
window_smooth = 20;      % Filtro media mobile per comprimere il rumore

% --- SELEZIONE CARTELLA ---
path_cartella = uigetdir('', 'Seleziona cartella con i file CSV');
if isequal(path_cartella, 0), return; end
lista_file = dir(fullfile(path_cartella, '*.csv'));

risultati = []; % Matrice per [P_media, Q_media, R_media]

fprintf('\n%-35s | %-10s | %-10s | %-10s\n', 'File Analizzato', 'P [Pa]', 'Q [L/s]', 'R [Pa*s/L]');
fprintf('----------------------------------------------------------------------------\n');

for i = 1:length(lista_file)
    fn = fullfile(path_cartella, lista_file(i).name);
    
    % 1. ESTRAZIONE VOLUME (Apertura sicura del file)
    v_siringa = NaN;
    fid = fopen(fn, 'r');
    if fid == -1, continue; end
    
    while ~feof(fid)
        linea = fgetl(fid);
        % FIX: Controlliamo che la riga sia effettivamente testo prima di usare 'contains'
        if ~ischar(linea), break; end 
        
        if contains(linea, 'Capacita', 'IgnoreCase', true)
            parti = strsplit(linea, ',');
            if length(parti) >= 2
                v_siringa = str2double(parti{2});
            end
        end
        if contains(linea, 'Time_s'), break; end
    end
    fclose(fid);
    
    if isnan(v_siringa), continue; end

    % 2. LETTURA DATI (Salto automatico intestazioni)
    data_raw = readmatrix(fn); 
    data_raw(any(isnan(data_raw), 2), :) = []; 
    
    if size(data_raw, 2) < 2, continue; end
    
    t = data_raw(:, 1);
    p = data_raw(:, 2);
    [t, idxU] = unique(t); p = p(idxU);
    
    % 3. CALCOLO FLUSSO ISTANTANEO Q(t) E FILTRAGGIO
    area_p = trapz(t, p);
    q_ist = (v_siringa .* p) ./ area_p;
    
    p_max = max(p);
    idx_v = find(p >= p_max * soglia_inf & p <= p_max * soglia_sup);
    
    if length(idx_v) > window_smooth
        % Compressione dati (Filtro base MATLAB)
        p_f = conv(p(idx_v), ones(window_smooth,1)/window_smooth, 'valid');
        q_f = conv(q_ist(idx_v), ones(window_smooth,1)/window_smooth, 'valid');
        
        % Media Robusta (Manuale per evitare dipendenza da Toolbox)
        p_rep = manual_trimmean(p_f, 15);
        q_rep = manual_trimmean(q_f, 15);
        r_rep = p_rep / q_rep;
        
        risultati = [risultati; p_rep, q_rep, r_rep];
        fprintf('%-35s | %10.2f | %10.3f | %10.3f\n', lista_file(i).name, p_rep, q_rep, r_rep);
    end
end

% --- RIEPILOGO FINALE A TERMINALE ---
num_punti = size(risultati, 1);
fprintf('----------------------------------------------------------------------------\n');
fprintf('ANALISI COMPLETATA\n');
fprintf('Numero totale di file processati con successo: %d\n', num_punti);
fprintf('Numero di file scartati (non conformi):        %d\n', length(lista_file) - num_punti);
fprintf('----------------------------------------------------------------------------\n\n');

% --- GRAFICI ---
if isempty(risultati), error('Nessun dato valido estratto dai file.'); end

[Q_s, sI] = sort(risultati(:,2)); R_s = risultati(sI, 3);
[P_s, sIP] = sort(risultati(:,1)); R_sP = risultati(sIP, 3);

q_vec = linspace(min(Q_s), max(Q_s), 200);
r_curve = interp1(Q_s, R_s, q_vec, metodo_interp);

figure('Color', 'w', 'Name', 'Caratterizzazione Resistenza Pneumotacografo');
subplot(1,2,1);
plot(risultati(:,2), risultati(:,3), 'o', 'MarkerEdgeColor', [0.4 0.4 0.4], 'DisplayName', 'Dati Mediati');
hold on; plot(q_vec, r_curve, 'r-', 'LineWidth', 2, 'DisplayName', 'Curva Caratteristica');
grid on; xlabel('Flusso Q [L/s]'); ylabel('Resistenza R [Pa*s/L]'); title('R vs Flusso'); legend('Location','best');

subplot(1,2,2);
plot(risultati(:,1), risultati(:,3), 'o', 'MarkerEdgeColor', [0.4 0.4 0.4]); 
hold on; plot(sort(risultati(:,1)), interp1(P_s, R_sP, sort(risultati(:,1)), metodo_interp), 'b-', 'LineWidth', 2);
grid on; xlabel('Pressione P [Pa]'); ylabel('Resistenza R [Pa*s/L]'); title('R vs Pressione');

%% FUNZIONE LOCALE: MEDIA TRONCATA
function m = manual_trimmean(data, percent)
    n = length(data);
    k = max(1, round(n * (percent / 100) / 2));
    if n <= 2*k, m = mean(data); return; end
    s_data = sort(data);
    m = mean(s_data(k+1 : end-k));
end